"""Centralized data directory resolver.

All data files (app.db, config.json, logs/, user_profile.md) are stored
under the directory returned by ``get_data_dir()``.

When the ``DATA_DIR`` environment variable is set (e.g. by Tauri passing its
appDataDir), that path is used.  Otherwise the project root is the default,
preserving the existing browser-mode behaviour.
"""

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent


def get_data_dir() -> Path:
    """Return the directory where runtime data files should be stored."""
    env_dir = os.environ.get("DATA_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    return _PROJECT_ROOT
