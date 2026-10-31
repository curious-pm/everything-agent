use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use serde::Serialize;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter};

const STOP_TIMEOUT: Duration = Duration::from_secs(30);
const RESTART_DELAY: Duration = Duration::from_secs(3);
const STOP_POLL: Duration = Duration::from_millis(100);

#[derive(Clone, Serialize, Debug)]
pub struct CoreState {
    pub state: String,
    pub label: String,
    pub detail: String,
}

impl CoreState {
    pub fn new(state: &str, label: &str, detail: &str) -> Self {
        Self { state: state.into(), label: label.into(), detail: detail.into() }
    }
}

pub struct Core {
    pub token: String,
    state: Mutex<CoreState>,
    stdin: Mutex<Option<ChildStdin>>,
    child: Mutex<Option<Child>>,
    pending: Mutex<HashMap<u64, mpsc::Sender<Value>>>,
    next_id: AtomicU64,
    stopping: AtomicBool,
    #[cfg(windows)]
    job: Mutex<Option<job::Job>>,
}

impl Core {
    pub fn new() -> Arc<Self> {
        Arc::new(Self {
            token: new_token(),
            state: Mutex::new(CoreState::new("STARTING", "Starting", "")),
            stdin: Mutex::new(None),
            child: Mutex::new(None),
            pending: Mutex::new(HashMap::new()),
            next_id: AtomicU64::new(1),
            stopping: AtomicBool::new(false),
            #[cfg(windows)]
            job: Mutex::new(job::Job::new()),
        })
    }

    pub fn state(&self) -> CoreState {
        self.state.lock().unwrap().clone()
    }

    pub fn start(self: &Arc<Self>, app: &AppHandle, exe: PathBuf) {
        let mut command = core_command(&exe);
        command.env("EVERYTHING_AGENT_CORE_TOKEN", &self.token).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            command.creation_flags(CREATE_NO_WINDOW);
        }
        let mut child = match command.spawn() {
            Ok(child) => child,
            Err(err) => {
                log::error!("Could not start the core {}: {err}", exe.display());
                self.set_state(app, CoreState::new("NO_CORE", "Couldn't start", &err.to_string()));
                return;
            }
        };
        #[cfg(windows)]
        if let Some(job) = self.job.lock().unwrap().as_ref() {
            job.assign(&child);
        }
        let stdout = child.stdout.take().expect("piped stdout");
        *self.stdin.lock().unwrap() = child.stdin.take();
        *self.child.lock().unwrap() = Some(child);

        let core = Arc::clone(self);
        let app = app.clone();
        thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                if let Ok(message) = serde_json::from_str::<Value>(&line) {
                    core.handle(&app, &message);
                }
            }
            core.exited(&app);
        });
    }

    fn handle(&self, app: &AppHandle, message: &Value) {
        match message["event"].as_str().unwrap_or_default() {
            "state" => self.set_state(app, CoreState::new(
                message["state"].as_str().unwrap_or_default(),
                message["label"].as_str().unwrap_or_default(),
                message["detail"].as_str().unwrap_or_default(),
            )),
            "reply" => {
                let sender = message["id"].as_u64().and_then(|id| self.pending.lock().unwrap().remove(&id));
                if let Some(sender) = sender {
                    let _ = sender.send(message["result"].clone());
                }
            }
            "already_running" => self.set_state(app, CoreState::new(
                "DAEMON_CONFLICT", "Already running",
                "Another copy of Everything Agent is running. Quit it from its tray icon, then start this one again.",
            )),
            _ => {}
        }
    }

    fn exited(self: &Arc<Self>, app: &AppHandle) {
        if let Some(mut child) = self.child.lock().unwrap().take() {
            let _ = child.wait();
        }
        self.close_stdin();
        self.pending.lock().unwrap().clear();
        if self.stopping.load(Ordering::SeqCst) || self.state().state == "DAEMON_CONFLICT" {
            return;
        }
        log::warn!("The core exited unexpectedly; restarting it");
        self.set_state(app, CoreState::new("RESTARTING", "Restarting after a problem", "the core stopped"));
        let core = Arc::clone(self);
        let app = app.clone();
        thread::spawn(move || {
            thread::sleep(RESTART_DELAY);
            if !core.stopping.load(Ordering::SeqCst) {
                crate::boot(&app, &core);
            }
        });
    }

    pub fn set_state(&self, app: &AppHandle, state: CoreState) {
        *self.state.lock().unwrap() = state.clone();
        crate::tray::on_state(app, &state);
        let _ = app.emit("core-state", state);
    }

    pub fn request(&self, mut command: Value, timeout: Duration) -> Result<Value, String> {
        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        command["id"] = json!(id);
        let (sender, receiver) = mpsc::channel();
        self.pending.lock().unwrap().insert(id, sender);
        if let Err(err) = self.send(&command) {
            self.pending.lock().unwrap().remove(&id);
            return Err(err);
        }
        receiver.recv_timeout(timeout).map_err(|_| {
            self.pending.lock().unwrap().remove(&id);
            "Reachy didn't answer in time".to_string()
        })
    }

    pub fn send(&self, command: &Value) -> Result<(), String> {
        let mut stdin = self.stdin.lock().unwrap();
        let pipe = stdin.as_mut().ok_or("Reachy isn't running")?;
        writeln!(pipe, "{command}").and_then(|_| pipe.flush()).map_err(|err| err.to_string())
    }

    #[cfg(windows)]
    pub fn outlive_shell(&self) {
        self.set_kill_with_shell(false);
    }

    #[cfg(windows)]
    pub fn bind_to_shell(&self) {
        self.set_kill_with_shell(true);
    }

    #[cfg(windows)]
    fn set_kill_with_shell(&self, kill: bool) {
        if let Some(job) = self.job.lock().unwrap().as_ref() {
            job.set_kill_on_close(kill);
        }
    }

    pub fn stop(&self) {
        self.stopping.store(true, Ordering::SeqCst);
        self.close_stdin();
        let deadline = Instant::now() + STOP_TIMEOUT;
        loop {
            {
                let mut guard = self.child.lock().unwrap();
                let Some(child) = guard.as_mut() else { return };
                match child.try_wait() {
                    Ok(Some(_)) | Err(_) => return,
                    Ok(None) if Instant::now() >= deadline => {
                        log::warn!("The core didn't stop in time; ending it");
                        let _ = child.kill();
                        return;
                    }
                    Ok(None) => {}
                }
            }
            thread::sleep(STOP_POLL);
        }
    }

    fn close_stdin(&self) {
        self.stdin.lock().unwrap().take();
    }
}

fn new_token() -> String {
    if cfg!(debug_assertions) {
        if let Ok(token) = std::env::var("REACHY_DEV_TOKEN") {
            return token;
        }
    }
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).expect("system randomness");
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn core_command(exe: &Path) -> Command {
    let mut command = Command::new(exe);
    if is_python(exe) {
        command.args(["-m", "everything_agent.desktop"]);
    }
    command.arg("--headless");
    command
}

pub fn dev_python() -> Option<PathBuf> {
    if !cfg!(debug_assertions) {
        return None;
    }
    let relative = if cfg!(windows) { ".venv/Scripts/python.exe" } else { ".venv/bin/python" };
    std::env::current_dir().ok()?.ancestors().map(|dir| dir.join(relative)).find(|path| path.is_file())
}

fn is_python(exe: &Path) -> bool {
    exe.file_stem().and_then(|stem| stem.to_str()).is_some_and(|stem| stem.starts_with("python"))
}

#[cfg(windows)]
mod job {
    use std::os::windows::io::AsRawHandle;
    use std::process::Child;

    use windows::Win32::Foundation::{CloseHandle, HANDLE};
    use windows::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation, SetInformationJobObject,
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };

    pub struct Job(HANDLE);

    unsafe impl Send for Job {}

    impl Job {
        pub fn new() -> Option<Self> {
            let handle = unsafe { CreateJobObjectW(None, windows::core::PCWSTR::null()) }.ok()?;
            let job = Self(handle);
            job.set_kill_on_close(true).then_some(job)
        }

        pub fn set_kill_on_close(&self, kill: bool) -> bool {
            let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
            if kill {
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            }
            unsafe {
                SetInformationJobObject(
                    self.0,
                    JobObjectExtendedLimitInformation,
                    &info as *const _ as *const core::ffi::c_void,
                    std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
                )
            }
            .is_ok()
        }

        pub fn assign(&self, child: &Child) {
            let process = HANDLE(child.as_raw_handle());
            if let Err(err) = unsafe { AssignProcessToJobObject(self.0, process) } {
                log::warn!("Could not put the core in a job object: {err}");
            }
        }
    }

    impl Drop for Job {
        fn drop(&mut self) {
            unsafe {
                let _ = CloseHandle(self.0);
            }
        }
    }
}
