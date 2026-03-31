import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=32)
def load_json_file(path: str) -> dict[str, Any]:
    """
    Load and cache a JSON file.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
