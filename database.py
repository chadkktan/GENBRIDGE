"""
A tiny JSON "database" wrapper:
- Load and save users.json / profiles.json safely
- Expose an in-memory db object (db.users / db.profiles)

Keeps file I/O in one place so routes stay clean.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any

from config import USERS_FILE, PROFILES_FILE


def _load_json(path: str) -> dict:
    """
    Load JSON file into dict safely.
    Returns {} if file doesn't exist or is invalid.
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_json(path: str, data: dict) -> None:
    """
    Save JSON safely using a temp file then atomic replace.
    Prevents corrupted files if write is interrupted.
    """
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


@dataclass
class JsonDB:
    """
    In-memory store backed by JSON files.

    users:
      email -> {full_name, pw_hash, created_at}

    profiles:
      email -> {first_name, last_name, ...}
    """

    users_file: str = USERS_FILE
    profiles_file: str = PROFILES_FILE

    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)

    def load(self) -> None:
        """Load both JSON files into memory."""
        self.users = _load_json(self.users_file)
        self.profiles = _load_json(self.profiles_file)

    def save_users(self) -> None:
        """Persist users dict to users.json."""
        _save_json(self.users_file, self.users)

    def save_profiles(self) -> None:
        """Persist profiles dict to profiles.json."""
        _save_json(self.profiles_file, self.profiles)


# Global shared DB object used across routes
db = JsonDB()
db.load()
