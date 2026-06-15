"""Storage for the standalone Media Generation Prompt Library.

ONE shared, model-agnostic collection of saved prompts. Each entry always keeps
the positive + negative prompt and a *tag* of the model that was selected when it
was saved — the tag is informational only: prompts are not model-specific, so any
entry can be populated onto whatever model is currently loaded. When
"preserve all parameters" is ticked, the entry also snapshots every
JSON-serialisable generation setting so a full setup can be reproduced.

Persisted to ``<cwd>/.mediagen_promptlib.json`` (cwd = the Wan2GP root) — the same
convention sibling saintorphan plugins use, so saved prompts live OUTSIDE this
plugin's git repo. Values are JSON scalars / lists of scalars only; reference
media (start / ref images, control video / audio, masks) is never stored.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger("mediagen_promptlib")

_LOCK = threading.RLock()
_CONFIG_NAME = ".mediagen_promptlib.json"
_KEY = "prompts"

# Identity / media / transient keys never kept in a "preserve all parameters"
# snapshot: model identity is stored separately as a tag, and media handles are
# session-bound (like ImageSuite, reference media isn't stored in the library).
# Prompt + negative live at the entry top level, so they're excluded here too.
_EXCLUDE = {
    "state", "model_type", "model_filename", "model_name", "settings_version",
    "prompt", "negative_prompt",
    "image_start", "image_end", "image_refs", "image_guide", "image_mask",
    "video_source", "video_guide", "video_guide2", "video_mask",
    "audio_guide", "audio_guide2", "audio_source",
    "image_prompt_type", "video_prompt_type", "audio_prompt_type",
    "frames_positions",
}


# --- persistence -----------------------------------------------------------

def _path() -> Path:
    # Stable location (cwd = Wan2GP root), independent of where the plugin lives.
    return Path(os.getcwd()) / _CONFIG_NAME


def _load() -> dict:
    try:
        data = json.loads(_path().read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _prompts(data: dict) -> dict:
    pl = data.get(_KEY)
    return pl if isinstance(pl, dict) else {}


def _write(data: dict) -> None:
    try:
        _path().write_text(json.dumps(data, indent=2))
    except Exception:
        logger.warning("Could not write %s", _path(), exc_info=True)


# --- public API ------------------------------------------------------------

def names() -> list[str]:
    """Saved entry names, sorted (the dropdown's choices)."""
    with _LOCK:
        return sorted(_prompts(_load()).keys())


def get(name: str) -> dict | None:
    """The stored entry for ``name`` (a copy), or None if absent."""
    if not name:
        return None
    with _LOCK:
        entry = _prompts(_load()).get(name)
        return dict(entry) if isinstance(entry, dict) else None


def save(name: str, entry: dict) -> list[str]:
    """Create or overwrite ``name`` with ``entry``. Returns the sorted name list."""
    name = (name or "").strip()
    if not name:
        return names()
    with _LOCK:
        data = _load()
        pl = data.get(_KEY)
        if not isinstance(pl, dict):
            pl = {}
        pl[name] = entry
        data[_KEY] = pl
        _write(data)
        return sorted(pl.keys())


def delete(name: str) -> list[str]:
    """Remove ``name`` if present. Returns the updated sorted name list."""
    with _LOCK:
        data = _load()
        pl = data.get(_KEY)
        if isinstance(pl, dict) and name in pl:
            del pl[name]
            data[_KEY] = pl
            _write(data)
        return sorted(pl.keys()) if isinstance(pl, dict) else []


# --- entry building --------------------------------------------------------

def make_entry(prompt, negative, model_type, model_name, settings=None) -> dict:
    """Build a library entry from the current prompt + model tag. When
    ``settings`` is given (preserve-all-parameters), also snapshot every
    JSON-able generation parameter from it (minus identity / media keys)."""
    entry = {
        "prompt": prompt or "",
        "negative_prompt": negative or "",
        "model_type": model_type or "",
        "model_name": model_name or "",
        "preserve": settings is not None,
    }
    if settings is not None:
        entry["params"] = _snapshot(settings)
    return entry


def _snapshot(settings: dict) -> dict:
    """Keep only JSON-serialisable scalars / lists of scalars, dropping identity,
    media and transient keys, so the saved setup stays clean and reloadable."""
    out: dict = {}
    for k, v in (settings or {}).items():
        if k in _EXCLUDE:
            continue
        if v is None or isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, (list, tuple)):
            out[k] = [x for x in v if isinstance(x, (str, int, float, bool))]
    return out
