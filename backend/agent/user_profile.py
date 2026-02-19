"""User profile management — reads and writes a markdown file that stores
information about the user relevant to their job search.

The file uses YAML frontmatter to store metadata (e.g. onboarding status)."""

import os
import re

from backend.data_dir import get_data_dir

DEFAULT_PROFILE_TEMPLATE = """---
onboarded: false
---
# User Profile

## Summary
_No summary yet. The AI assistant will fill this in as it learns about you._

## Education
- _Not yet provided_

## Work Experience
- _Not yet provided_

## Skills & Expertise
- _Not yet provided_

## Fields of Interest
- _Not yet provided_

## Salary Preferences
- _Not yet provided_

## Location Preferences
- _Not yet provided_

## Remote Work Preferences
- _Not yet provided_

## Job Search Goals
- _Not yet provided_

## Other Notes
- _None yet_
"""

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def get_profile_path() -> str:
    """Return the absolute path to the user profile markdown file."""
    return str(get_data_dir() / "user_profile.md")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split *text* into a frontmatter dict and body string."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_str = m.group(1)
    body = text[m.end():]
    meta = {}
    for line in fm_str.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip()
            if val.lower() in ("true", "false"):
                val = val.lower() == "true"
            meta[key.strip()] = val
    return meta, body


def _serialize_frontmatter(meta: dict, body: str) -> str:
    """Combine *meta* dict and markdown *body* into a full document."""
    lines = []
    for k, v in meta.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            lines.append(f"{k}: {v}")
    fm = "\n".join(lines)
    return f"---\n{fm}\n---\n{body}"


def read_profile() -> str:
    """Read the user profile markdown (body only, no frontmatter).
    Returns the default template body if the file doesn't exist yet."""
    path = get_profile_path()
    if not os.path.exists(path):
        _, body = _parse_frontmatter(DEFAULT_PROFILE_TEMPLATE)
        return body
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    _, body = _parse_frontmatter(content)
    return body


def read_profile_raw() -> str:
    """Read the full file including frontmatter."""
    path = get_profile_path()
    if not os.path.exists(path):
        return DEFAULT_PROFILE_TEMPLATE
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_profile(content: str) -> None:
    """Overwrite the profile body, preserving frontmatter."""
    path = get_profile_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        meta, _ = _parse_frontmatter(existing)
    else:
        meta, _ = _parse_frontmatter(DEFAULT_PROFILE_TEMPLATE)
    # If the incoming content has its own frontmatter, strip it and merge
    incoming_meta, body = _parse_frontmatter(content)
    if incoming_meta:
        meta.update(incoming_meta)
    else:
        body = content
    full = _serialize_frontmatter(meta, body)
    with open(path, "w", encoding="utf-8") as f:
        f.write(full)


def ensure_profile_exists() -> None:
    """Create the profile file with the default template if it doesn't exist."""
    path = get_profile_path()
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_PROFILE_TEMPLATE)


def get_onboarding_state() -> str:
    """Return the onboarding state: 'not_started', 'in_progress', or 'completed'."""
    path = get_profile_path()
    if not os.path.exists(path):
        return "not_started"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    meta, _ = _parse_frontmatter(content)
    val = meta.get("onboarded", False)
    if val is True:
        return "completed"
    if val == "in_progress":
        return "in_progress"
    return "not_started"


def is_onboarded() -> bool:
    """Return True if the user has completed onboarding."""
    return get_onboarding_state() == "completed"


def is_onboarding_in_progress() -> bool:
    """Return True if onboarding was started but not completed."""
    return get_onboarding_state() == "in_progress"


def set_onboarding_in_progress() -> None:
    """Mark onboarding as started but not yet completed."""
    _set_onboarded_value("in_progress")


def set_onboarded(value: bool = True) -> None:
    """Set the onboarded flag in the profile frontmatter."""
    _set_onboarded_value(value)


def _set_onboarded_value(value) -> None:
    """Set the onboarded field to an arbitrary value (bool or string)."""
    ensure_profile_exists()
    path = get_profile_path()
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    meta, body = _parse_frontmatter(content)
    meta["onboarded"] = value
    full = _serialize_frontmatter(meta, body)
    with open(path, "w", encoding="utf-8") as f:
        f.write(full)
