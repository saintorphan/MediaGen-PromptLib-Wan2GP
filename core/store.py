"""Storage for the standalone Media Generation Prompt Library.

ONE shared, model-agnostic collection of saved prompts. Each entry always keeps
the positive + negative prompt and a *tag* of the model that was selected when it
was saved — the tag is informational only: prompts are not model-specific, so any
entry can be populated onto whatever model is currently loaded. When
"preserve all parameters" is ticked, the entry also snapshots every
JSON-serialisable generation setting so a full setup can be reproduced.

Persisted to ``<wan2gp-root>/.mediagen_promptlib.json`` (the directory Wan2GP was
launched from, snapshotted once at import — the same convention sibling
saintorphan plugins use, so saved prompts live OUTSIDE this plugin's git repo).
Values are JSON scalars / lists of scalars only; reference media (start / ref
images, control video / audio, masks) is never stored.

Durability: writes are atomic (temp file + fsync + os.replace), so a crash or
full disk never leaves a truncated primary file; a present-but-unreadable file is
backed up aside rather than silently overwritten; and write failures are reported
back to the caller (never a false "saved"). The in-process RLock serialises the
read-modify-write sequence; cross-process access (two Wan2GP instances launched
from the same directory) is intentionally last-writer-wins — atomic writes keep
that benign (a lost update, never a corrupt file).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger("mediagen_promptlib")

_LOCK = threading.RLock()
_CONFIG_NAME = ".mediagen_promptlib.json"
_KEY = "prompts"

# Snapshot the launch directory once at import (cwd == the host's pinned wgp_root
# at plugin-load time). Reading os.getcwd() per call would expose the data
# location to any in-session os.chdir(); pinning it here keeps the file stable.
_BASE_DIR = Path(os.getcwd())

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
    return _BASE_DIR / _CONFIG_NAME


def _read_raw() -> tuple[dict, bool]:
    """Return ``(data, corrupt)``. ``data`` is the parsed top-level dict, or
    ``{}`` when the file is absent / empty (both legitimately "no library yet").
    ``corrupt`` is True only when the file EXISTS and is non-empty but cannot be
    read or does not parse to a dict — the caller must not silently overwrite it
    without first preserving a copy (see ``_backup_corrupt``)."""
    p = _path()
    if not p.exists():
        return {}, False
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        logger.warning("Could not read %s", p, exc_info=True)
        return {}, True
    if not text.strip():
        return {}, False
    try:
        data = json.loads(text)
    except Exception:
        logger.warning("Malformed JSON in %s", p, exc_info=True)
        return {}, True
    if not isinstance(data, dict):
        logger.warning("Unexpected top-level type in %s (%s)", p, type(data).__name__)
        return {}, True
    return data, False


def _backup_corrupt() -> None:
    """Move an unreadable file aside so a save/delete never destroys it."""
    p = _path()
    try:
        bak = p.with_name(p.name + f".bak-{int(time.time())}")
        p.replace(bak)
        logger.warning("Backed up unreadable %s to %s before rewriting", p, bak)
    except Exception:
        logger.warning("Could not back up unreadable %s", p, exc_info=True)


def _load() -> dict:
    """Top-level dict for read-only callers (a corrupt file reads as empty,
    without touching it on disk)."""
    return _read_raw()[0]


def _prompts(data: dict) -> dict:
    pl = data.get(_KEY)
    return pl if isinstance(pl, dict) else {}


def _write(data: dict) -> bool:
    """Atomically persist ``data``. Returns True on success, False (after
    logging) on any failure — callers must surface a failure rather than report
    a false success."""
    p = _path()
    tmp = p.with_name(p.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)  # atomic on POSIX and Windows
        return True
    except Exception:
        logger.warning("Could not write %s", p, exc_info=True)
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        return False


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


def save(name: str, entry: dict) -> list[str] | None:
    """Create or overwrite ``name`` with ``entry``. Returns the sorted name list
    on success, or ``None`` if the entry could not be persisted to disk."""
    name = (name or "").strip()
    if not name:
        return names()
    with _LOCK:
        data, corrupt = _read_raw()
        if corrupt:
            _backup_corrupt()  # never clobber an unreadable file without a copy
        pl = data.get(_KEY)
        if not isinstance(pl, dict):
            pl = {}
        pl[name] = entry
        data[_KEY] = pl
        if not _write(data):
            return None
        return sorted(pl.keys())


def delete(name: str) -> list[str] | None:
    """Remove ``name`` if present. Returns the updated sorted name list, or
    ``None`` if a needed write to disk failed."""
    with _LOCK:
        data, corrupt = _read_raw()
        if corrupt:
            _backup_corrupt()
        pl = data.get(_KEY)
        if isinstance(pl, dict) and name in pl:
            del pl[name]
            data[_KEY] = pl
            if not _write(data):
                return None
            return sorted(pl.keys())
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


def sanitize_params(params) -> dict:
    """Filter a stored ``params`` dict on LOAD with the same rules Save applies,
    so a hand-edited / shared library file can't inject identity, media, or
    non-scalar values straight into the live settings dict on populate."""
    return _snapshot(params if isinstance(params, dict) else {})


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
