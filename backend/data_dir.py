"""Centralized data directory resolver.

All user data files (app.db, telemetry.db, config.json, logs/,
user_profile.md, resumes/) are stored under the directory returned by
``get_data_dir()``.

When the ``DATA_DIR`` environment variable is set (e.g. by Tauri passing its
appDataDir), that path is used.  Otherwise ``<project_root>/user_data/`` is
the default, keeping user data separate from source code.
"""

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "user_data"


def get_data_dir() -> Path:
    """Return the directory where runtime data files should be stored."""
    env_dir = os.environ.get("DATA_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    _DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DEFAULT_DATA_DIR
