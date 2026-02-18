use tauri::Manager;
use tauri_plugin_shell::ShellExt;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
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

                let (mut _rx, _child) = sidecar.spawn().expect("failed to spawn sidecar");

                eprintln!("[tauri] Flask sidecar started with data-dir: {:?}", app_data_dir);
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
