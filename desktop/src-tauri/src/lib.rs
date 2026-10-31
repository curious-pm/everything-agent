mod core;
#[cfg(windows)]
mod session;
mod tray;

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use serde_json::json;
use tauri::{AppHandle, Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

use crate::core::{Core, CoreState};

static QUITTING: AtomicBool = AtomicBool::new(false);
const APP_NAME: &str = "Everything Agent";
const MAIN_WINDOW: &str = "main";
const HIDDEN_ARG: &str = "--hidden";
const DEFAULT_WEB_PORT: u16 = 8042;
const DAEMON_PORT: u16 = 8000;
const CORE_NAME: &str = "Everything Agent Core";

pub const MUTE_SHORTCUT_LABEL: &str = if cfg!(target_os = "macos") { "Cmd+Alt+M" } else { "Ctrl+Alt+M" };

fn mute_shortcut() -> Shortcut {
    let modifiers = if cfg!(target_os = "macos") { Modifiers::SUPER | Modifiers::ALT } else { Modifiers::CONTROL | Modifiers::ALT };
    Shortcut::new(Some(modifiers), Code::KeyM)
}

#[tauri::command]
fn core_state(core: State<'_, Arc<Core>>) -> CoreState {
    core.state()
}

#[tauri::command]
fn get_autostart(app: AppHandle) -> bool {
    app.autolaunch().is_enabled().unwrap_or(false)
}

#[tauri::command]
fn set_autostart(app: AppHandle, enabled: bool) -> Result<bool, String> {
    let launcher = app.autolaunch();
    if enabled { launcher.enable() } else { launcher.disable() }.map_err(|err| err.to_string())?;
    Ok(launcher.is_enabled().unwrap_or(false))
}

pub fn begin_quit() -> bool {
    !QUITTING.swap(true, Ordering::SeqCst)
}

pub fn quit_app(app: &AppHandle) {
    if !begin_quit() {
        return;
    }
    if let Some(window) = app.get_webview_window(MAIN_WINDOW) {
        let _ = window.hide();
    }
    let app = app.clone();
    std::thread::spawn(move || {
        if let Some(core) = app.try_state::<Arc<Core>>() {
            core.stop();
        }
        app.exit(0);
    });
}

pub fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window(MAIN_WINDOW) {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn user_settings_file(app: &AppHandle) -> Option<PathBuf> {
    let base = if cfg!(target_os = "linux") { app.path().config_dir() } else { app.path().local_data_dir() };
    Some(base.ok()?.join("everything_agent").join(".env"))
}

fn web_port(app: &AppHandle) -> u16 {
    user_settings_file(app)
        .and_then(|path| std::fs::read_to_string(path).ok())
        .and_then(|text| {
            text.lines()
                .find_map(|line| line.trim().strip_prefix("WEB_PORT=").map(|v| v.trim().trim_matches('"').to_string()))
        })
        .and_then(|value| value.parse().ok())
        .unwrap_or(DEFAULT_WEB_PORT)
}

fn create_main_window(app: &AppHandle, core: &Core, visible: bool) {
    let host = json!({
        "apiBase": format!("http://127.0.0.1:{}", web_port(app)),
        "token": core.token,
        "daemonBase": format!("http://127.0.0.1:{DAEMON_PORT}"),
    });
    let init = if cfg!(debug_assertions) {
        format!("window.__EVERYTHING_AGENT__ = {host};")
    } else {
        format!("if (location.protocol === 'tauri:' || location.hostname === 'tauri.localhost') window.__EVERYTHING_AGENT__ = {host};")
    };
    let built = WebviewWindowBuilder::new(app, MAIN_WINDOW, WebviewUrl::App("index.html".into()))
        .title(APP_NAME)
        .inner_size(1100.0, 800.0)
        .min_inner_size(420.0, 480.0)
        .visible(visible)
        .initialization_script(&init)
        .build();
    if let Err(err) = built {
        log::error!("Could not open the window: {err}");
    }
}

fn tell_page_visible(window: &tauri::Window) {
    let visible = window.is_visible().unwrap_or(true) && !window.is_minimized().unwrap_or(false);
    if let Some(webview) = window.app_handle().get_webview_window(window.label()) {
        let _ = webview.eval(format!("window.dispatchEvent(new CustomEvent('everything-agent-visibility', {{ detail: {visible} }}))"));
    }
}

fn bundled_core(app: &AppHandle) -> Option<PathBuf> {
    let exe = if cfg!(windows) { format!("{CORE_NAME}.exe") } else { CORE_NAME.to_string() };
    let path = app.path().resource_dir().ok()?.join("core").join(CORE_NAME).join(exe);
    path.is_file().then_some(path)
}

pub fn boot(app: &AppHandle, core: &Arc<Core>) {
    if let Some(exe) = std::env::var_os("EVERYTHING_AGENT_CORE_EXE").filter(|_| cfg!(debug_assertions)) {
        core.start(app, exe.into());
    } else if let Some(exe) = bundled_core(app) {
        core.start(app, exe);
    } else if let Some(python) = core::dev_python() {
        log::info!("No bundled core; using the repo's Python");
        core.start(app, python);
    } else {
        core.set_state(app, CoreState::new("NO_CORE", "Part of Reachy is missing", "Reinstall Everything Agent."));
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show_main(app)))
        .plugin(tauri_plugin_autostart::Builder::new().app_name(APP_NAME).arg(HIDDEN_ARG).build())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_opener::init())
        .plugin(
            tauri_plugin_log::Builder::new()
                .level(log::LevelFilter::Info)
                .target(tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::LogDir { file_name: Some("shell".into()) }))
                .build(),
        )
        .invoke_handler(tauri::generate_handler![core_state, get_autostart, set_autostart])
        .setup(|app| {
            let hidden = std::env::args().any(|arg| arg == HIDDEN_ARG);
            let core = Core::new();
            app.manage(Arc::clone(&core));
            tray::build(app.handle(), Arc::clone(&core))?;
            #[cfg(windows)]
            session::watch(Arc::clone(&core));

            let shortcut = mute_shortcut();
            let shortcut_core = Arc::clone(&core);
            app.handle().plugin(
                tauri_plugin_global_shortcut::Builder::new()
                    .with_handler(move |app, pressed, event| {
                        if pressed == &shortcut && event.state() == ShortcutState::Pressed {
                            tray::spawn_toggle_mute(app, &shortcut_core, "mic");
                        }
                    })
                    .build(),
            )?;
            if let Err(err) = app.global_shortcut().register(shortcut) {
                log::warn!("Could not register {MUTE_SHORTCUT_LABEL}: {err}");
            }
            create_main_window(app.handle(), &core, !hidden);
            let (handle, boot_core) = (app.handle().clone(), Arc::clone(&core));
            std::thread::spawn(move || boot(&handle, &boot_core));
            Ok(())
        })
        .on_window_event(|window, event| match event {
            WindowEvent::CloseRequested { api, .. } if window.label() == MAIN_WINDOW => {
                api.prevent_close();
                quit_app(window.app_handle());
            }
            WindowEvent::Resized(_) | WindowEvent::Focused(_) if window.label() == MAIN_WINDOW => tell_page_visible(window),
            _ => {}
        })
        .build(tauri::generate_context!())
        .expect("error while building the Everything Agent shell")
        .run(|app, event| {
            if let RunEvent::ExitRequested { api, .. } = event {
                if !QUITTING.load(Ordering::SeqCst) {
                    api.prevent_exit();
                    quit_app(app);
                }
            }
        });
}
