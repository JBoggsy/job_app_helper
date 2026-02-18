import argparse
import os

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
    app.run(debug=True, port=args.port)
