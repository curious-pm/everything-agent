use std::sync::{Arc, OnceLock};
use std::thread;

use windows::core::w;
use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::System::Shutdown::{ShutdownBlockReasonCreate, ShutdownBlockReasonDestroy};
use windows::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DispatchMessageW, GetMessageW, RegisterClassW, TranslateMessage, MSG,
    WINDOW_EX_STYLE, WINDOW_STYLE, WM_ENDSESSION, WM_QUERYENDSESSION, WNDCLASSW,
};

use crate::core::Core;

static CORE: OnceLock<Arc<Core>> = OnceLock::new();

pub fn watch(core: Arc<Core>) {
    if CORE.set(core).is_err() {
        return;
    }
    thread::spawn(|| unsafe {
        let instance = GetModuleHandleW(None).unwrap_or_default();
        let class = w!("EverythingAgentShellSession");
        let wc = WNDCLASSW { lpfnWndProc: Some(window_proc), hInstance: instance.into(), lpszClassName: class, ..Default::default() };
        if RegisterClassW(&wc) == 0 {
            log::warn!("Could not register the session window");
            return;
        }
        let window = CreateWindowExW(
            WINDOW_EX_STYLE(0), class, w!("Everything Agent"), WINDOW_STYLE(0), 0, 0, 0, 0, None, None, Some(instance.into()), None,
        );
        if window.is_err() {
            log::warn!("Could not create the session window");
            return;
        }
        let mut msg = MSG::default();
        while GetMessageW(&mut msg, None, 0, 0).as_bool() {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    });
}

unsafe extern "system" fn window_proc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    match msg {
        WM_QUERYENDSESSION => {
            if let Some(core) = CORE.get() {
                core.outlive_shell();
            }
            let _ = ShutdownBlockReasonCreate(hwnd, w!("Putting Reachy to sleep"));
            LRESULT(1)
        }
        WM_ENDSESSION => {
            let session_ending = wparam.0 != 0;
            if session_ending {
                log::info!("Windows is ending the session; stopping Reachy");
                crate::begin_quit();
                if let Some(core) = CORE.get() {
                    core.stop();
                }
            } else if let Some(core) = CORE.get() {
                core.bind_to_shell();
            }
            let _ = ShutdownBlockReasonDestroy(hwnd);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}
