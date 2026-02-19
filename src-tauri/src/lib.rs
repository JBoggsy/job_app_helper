use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// Holds the sidecar process handle and its PID for process-tree cleanup.
struct Sidecar {
    child: CommandChild,
    pid: u32,
}

/// Kill the sidecar **and all its child processes**.
///
/// PyInstaller `--onefile` binaries fork on Linux: the bootloader becomes the
/// parent (the PID that Tauri knows about) and the actual Python/Flask process
/// runs as a child.  `CommandChild::kill()` only sends SIGKILL to the parent
/// bootloader — the child is orphaned and keeps the port bound.
///
/// We therefore kill child processes first with `pkill -KILL -P <pid>`, then
/// kill the bootloader via `CommandChild::kill()`.
fn kill_sidecar(sidecar: &mut Option<Sidecar>) {
    if let Some(s) = sidecar.take() {
        let pid = s.pid;
        eprintln!("[tauri] Killing Flask sidecar process tree (PID {pid})...");

        // 1. Kill child processes spawned by the sidecar (PyInstaller subprocess).
        #[cfg(unix)]
        {
            let _ = std::process::Command::new("pkill")
                .args(["-KILL", "-P", &pid.to_string()])
                .status();
        }
        #[cfg(windows)]
        {
            // taskkill /T kills the entire process tree rooted at the given PID.
            let _ = std::process::Command::new("taskkill")
                .args(["/T", "/F", "/PID", &pid.to_string()])
                .status();
        }

        // 2. Kill the sidecar bootloader process itself.
        let _ = s.child.kill();
    }
}

/// Kill any stale flask-backend processes left over from a previous run that
/// didn't shut down cleanly (e.g. crash, SIGKILL without cleanup).
#[cfg(not(debug_assertions))]
fn cleanup_stale_sidecars() {
    eprintln!("[tauri] Cleaning up stale flask-backend processes...");
    #[cfg(unix)]
    {
        let _ = std::process::Command::new("pkill")
            .args(["-KILL", "flask-backend"])
            .status();
    }
    #[cfg(windows)]
    {
        let _ = std::process::Command::new("taskkill")
            .args(["/F", "/IM", "flask-backend.exe"])
            .status();
    }
}

pub fn run() {
    // Clean up stale sidecar processes from previous runs before spawning a new one.
    #[cfg(not(debug_assertions))]
    cleanup_stale_sidecars();

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

                let pid = child.pid();
                eprintln!("[tauri] Flask sidecar started (PID {pid}) with data-dir: {app_data_dir:?}");

                app.manage(Mutex::new(Some(Sidecar { child, pid })));
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            match event {
                // Kill sidecar when the window is destroyed (normal close).
                tauri::RunEvent::WindowEvent {
                    event: tauri::WindowEvent::Destroyed,
                    ..
                } => {
                    if let Some(state) = app_handle.try_state::<Mutex<Option<Sidecar>>>() {
                        if let Ok(mut guard) = state.lock() {
                            kill_sidecar(&mut guard);
                        }
                    }
                }
                // Also kill on app exit as a final safety net.
                tauri::RunEvent::Exit => {
                    if let Some(state) = app_handle.try_state::<Mutex<Option<Sidecar>>>() {
                        if let Ok(mut guard) = state.lock() {
                            kill_sidecar(&mut guard);
                        }
                    }
                }
                _ => {}
            }
        });
}
