"""
Central place for app configuration:
- Project base paths
- Upload/data folders
- Constants like allowed image extensions
- A helper to create required folders
"""

import os

# Absolute path to the folder containing this file (project root)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Flask secret key for session cookies (change this for production)
SECRET_KEY = "dev-secret-change-me"

# Where uploaded avatars/images will be saved
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

# Where your JSON files live (users.json / profiles.json)
DATA_DIR = os.path.join(BASE_DIR, "data")

USERS_FILE = os.path.join(DATA_DIR, "users.json")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")

# Allowed avatar upload file extensions
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


# Make sure folders exist before the app starts.
def ensure_dirs() -> None:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
