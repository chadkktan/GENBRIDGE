"""
Central configuration for the messaging app:
- Project base paths
- Upload/data folders
- Allowed file types for avatars and media messages
- App constants like max file size
- Helper to create required folders before app start
"""

import os

# --------------------------
# Base paths
# --------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Project root

# Folder for media messages (images, videos, audio)
MEDIA_FOLDER = os.path.join(BASE_DIR, "static", "media")

# Folder for JSON data storage
DATA_DIR = os.path.join(BASE_DIR, "data")

# --------------------------
# JSON files
# --------------------------
COMMUNITY_FILE = os.path.join(DATA_DIR, "communitycontent.json")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")
MESSAGES_FILE = os.path.join(DATA_DIR, "chats.json")
MEDIA_MESSAGES_FILE = os.path.join(DATA_DIR, "media.json")

# --------------------------
# Flask & app constants
# --------------------------
SECRET_KEY = "dev-secret-change-me"  # Change for production
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size

# Allowed file extensions for avatars and media messages
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "mp4", "mp3"}

# --------------------------
# Helper functions
# --------------------------
def ensure_dirs() -> None:
    """
    Ensure all required folders exist before the app starts.
    """
    os.makedirs(MEDIA_FOLDER, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
