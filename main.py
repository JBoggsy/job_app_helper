import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

parser = argparse.ArgumentParser(description="Job Application Helper backend server")
parser.add_argument("--data-dir", help="Directory for app data files (db, config, logs, profile)")
parser.add_argument("--port", type=int, default=5000, help="Port to run the server on")
args = parser.parse_args()

if args.data_dir:
    os.environ["DATA_DIR"] = args.data_dir

from backend.app import create_app  # noqa: E402 — must import after DATA_DIR is set

app = create_app()

if __name__ == "__main__":
    # When running as a frozen PyInstaller binary (Tauri sidecar), disable debug
    # mode. debug=True enables Werkzeug's auto-reloader, which spawns a child
    # subprocess. When Tauri kills the sidecar, that child becomes orphaned and
    # keeps the port bound.
    is_frozen = getattr(sys, "frozen", False)
    app.run(debug=not is_frozen, port=args.port)
