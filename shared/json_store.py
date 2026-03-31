from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_file_exists(path: str | Path, default: dict[str, Any] | list[Any] | None = None) -> Path:
    """
    Ensure that a JSON file exists.

    Behavior:
    - create parent directories if needed
    - create the file only if it does not already exist
    - never overwrite an existing file
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    if not p.exists():
        if default is None:
            default = {}
        p.write_text(
            json.dumps(default, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return p


def load_json_or_default(path: str | Path, default: dict[str, Any] | list[Any] | None = None) -> Any:
    """
    Load JSON from disk.

    If the file does not exist, it is created with the provided default.
    If parsing fails, the default value is returned without overwriting the file.
    """
    p = ensure_file_exists(path, default=default)

    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        if default is None:
            return {}
        return default


def save_json_atomic(path: str | Path, payload: Any) -> Path:
    """
    Save JSON atomically.

    Writes to a temporary file first, then replaces the target file.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = p.with_suffix(p.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(p)

    return p


class JSONStore:
    """
    Small helper for persistent JSON storage.
    """

    def __init__(self, path: str | Path, default: dict[str, Any] | list[Any] | None = None) -> None:
        self.path = Path(path)
        self.default = {} if default is None else default
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_exists(self) -> Path:
        """
        Create the JSON file only if it does not already exist.
        """
        return ensure_file_exists(self.path, self.default)

    def load(self) -> Any:
        """
        Load JSON from disk or return the default value on parse failure.
        """
        return load_json_or_default(self.path, self.default)

    def save(self, payload: Any) -> Path:
        """
        Save JSON atomically.
        """
        return save_json_atomic(self.path, payload)
