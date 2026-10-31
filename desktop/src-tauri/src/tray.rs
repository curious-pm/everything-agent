use std::sync::Arc;
use std::thread;
use std::time::Duration;

use serde_json::{json, Value};
use tauri::image::Image;
use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIcon, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, Wry};
use tauri_plugin_autostart::ManagerExt;

use crate::core::{Core, CoreState};

const MUTE_POLL: Duration = Duration::from_secs(2);
const REQUEST_TIMEOUT: Duration = Duration::from_secs(5);
const WINDOWS_TOOLTIP_MAX_CHARS: usize = 127;
const DOT_SIZE: u32 = 32;

pub struct Tray {
    icon: TrayIcon,
    status: MenuItem<Wry>,
    mic: CheckMenuItem<Wry>,
    speaker: CheckMenuItem<Wry>,
}

pub fn build(app: &AppHandle, core: Arc<Core>) -> tauri::Result<()> {
    let status = MenuItem::with_id(app, "status", "Reachy: Starting", false, None::<&str>)?;
    let open = MenuItem::with_id(app, "open", "Open Reachy", true, None::<&str>)?;
    let mic = CheckMenuItem::with_id(
        app, "mute_mic", format!("Mute Reachy's microphone ({})", crate::MUTE_SHORTCUT_LABEL), true, false, None::<&str>,
    )?;
    let speaker = CheckMenuItem::with_id(app, "mute_speaker", "Mute Reachy's speaker", true, false, None::<&str>)?;
    let restart = MenuItem::with_id(app, "restart", "Restart Reachy", true, None::<&str>)?;
    let autostart_on = app.autolaunch().is_enabled().unwrap_or(false);
    let autostart = CheckMenuItem::with_id(app, "autostart", "Start at login", true, autostart_on, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit Reachy", true, None::<&str>)?;
    let separator = || PredefinedMenuItem::separator(app);
    let menu = Menu::with_items(app, &[
        &status, &open, &separator()?, &mic, &speaker, &separator()?, &restart, &autostart, &separator()?, &quit,
    ])?;

    let icon = TrayIconBuilder::with_id("main")
        .icon(dot("STARTING"))
        .tooltip("Everything Agent: Starting")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(move |app, event| match event.id.as_ref() {
            "open" => crate::show_main(app),
            "mute_mic" => spawn_toggle_mute(app, &core, "mic"),
            "mute_speaker" => spawn_toggle_mute(app, &core, "speaker"),
            "restart" => {
                let _ = core.send(&json!({ "cmd": "restart" }));
            }
            "autostart" => {
                let launcher = app.autolaunch();
                let _ = if launcher.is_enabled().unwrap_or(false) { launcher.disable() } else { launcher.enable() };
            }
            "quit" => crate::quit_app(app),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                crate::show_main(tray.app_handle());
            }
        })
        .build(app)?;

    app.manage(Tray { icon, status, mic, speaker });
    spawn_mute_sync(app.clone());
    Ok(())
}

pub fn on_state(app: &AppHandle, state: &CoreState) {
    let Some(tray) = app.try_state::<Tray>() else { return };
    let label = if state.label.is_empty() { &state.state } else { &state.label };
    let _ = tray.status.set_text(format!("Reachy: {label}"));
    let _ = tray.icon.set_icon(Some(dot(&state.state)));
    let tooltip: String = format!("Everything Agent: {label}").chars().take(WINDOWS_TOOLTIP_MAX_CHARS).collect();
    let _ = tray.icon.set_tooltip(Some(tooltip));
}

pub fn spawn_toggle_mute(app: &AppHandle, core: &Arc<Core>, which: &'static str) {
    let (app, core) = (app.clone(), Arc::clone(core));
    thread::spawn(move || toggle_mute(&app, &core, which));
}

fn toggle_mute(app: &AppHandle, core: &Core, which: &str) {
    let Ok(current) = get_mute(core) else { return };
    let muted = current[which].as_bool().unwrap_or(false);
    let mut command = json!({ "cmd": "mute" });
    command[which] = json!(!muted);
    if let Ok(state) = core.request(command, REQUEST_TIMEOUT) {
        show_mute(app, &state);
    }
}

fn get_mute(core: &Core) -> Result<Value, String> {
    core.request(json!({ "cmd": "get_mute" }), REQUEST_TIMEOUT)
}

fn spawn_mute_sync(app: AppHandle) {
    thread::spawn(move || loop {
        thread::sleep(MUTE_POLL);
        let Some(core) = app.try_state::<Arc<Core>>() else { continue };
        if core.state().state != "RUNNING" {
            continue;
        }
        if let Ok(state) = get_mute(&core) {
            show_mute(&app, &state);
        }
    });
}

fn show_mute(app: &AppHandle, state: &Value) {
    if let Some(tray) = app.try_state::<Tray>() {
        let _ = tray.mic.set_checked(state["mic"].as_bool().unwrap_or(false));
        let _ = tray.speaker.set_checked(state["speaker"].as_bool().unwrap_or(false));
    }
}

fn dot(state: &str) -> Image<'static> {
    let (r, g, b) = match state {
        "RUNNING" => (0x2e, 0x9d, 0x55),
        "ROBOT_NOT_FOUND" | "DAEMON_CONFLICT" => (0xd0, 0x8a, 0x1a),
        "RESTARTING" | "NO_CORE" => (0xc8, 0x43, 0x2f),
        _ => (0x8a, 0x8a, 0x85),
    };
    let mut rgba = Vec::with_capacity((DOT_SIZE * DOT_SIZE * 4) as usize);
    let centre = (DOT_SIZE as f32 - 1.0) / 2.0;
    for y in 0..DOT_SIZE {
        for x in 0..DOT_SIZE {
            let distance = ((x as f32 - centre).powi(2) + (y as f32 - centre).powi(2)).sqrt();
            let alpha = ((centre - distance).clamp(0.0, 1.0) * 255.0) as u8;
            rgba.extend_from_slice(&[r, g, b, alpha]);
        }
    }
    Image::new_owned(rgba, DOT_SIZE, DOT_SIZE)
}
