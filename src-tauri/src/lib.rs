use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                eprintln!("[tauri] Debug mode — start Flask manually: uv run python main.py");
            } else {
                let app_data_dir = app
                    .path()
                    .app_data_dir()
                    .expect("failed to resolve appDataDir");

                std::fs::create_dir_all(&app_data_dir)
                    .expect("failed to create appDataDir");

                let sidecar = app
                    .shell()
                    .sidecar("flask-backend")
                    .expect("failed to create sidecar command")
                    .args([
                        "--data-dir",
                        app_data_dir.to_str().unwrap(),
                        "--port",
                        "5000",
                    ]);

                let (_rx, child) = sidecar.spawn().expect("failed to spawn sidecar");

                // Keep the child handle in managed state so it outlives setup
                // and can be killed when the window is destroyed.
                app.manage(Mutex::new(Some(child)));

                eprintln!("[tauri] Flask sidecar started with data-dir: {:?}", app_data_dir);
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window
                    .app_handle()
                    .try_state::<Mutex<Option<CommandChild>>>()
                {
                    if let Ok(mut child) = state.lock() {
                        if let Some(c) = child.take() {
                            let _ = c.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
