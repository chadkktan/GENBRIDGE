"""
Implements "Active Sessions" tracking:
- Uses Flask session cookie to store a session_id for each browser/device
- Tracks ACTIVE_SESSIONS server-side in memory (resets on restart)
- Provides helper functions for templates (humanized last seen)
"""

import uuid
from datetime import datetime

from flask import request, session


# Active sessions stored in memory:
# email -> [ {id, device, location, last_seen}, ... ]
ACTIVE_SESSIONS: dict[str, list[dict]] = {}


# Returns a stable ID for this browser session.
# Stored in Flask session cookie.
def get_or_create_session_id() -> str:
    sid = session.get("session_id")
    if not sid:
        sid = uuid.uuid4().hex
        session["session_id"] = sid
    return sid


# Simple readable label derived from user-agent.
def _device_label() -> str:
    ua = request.user_agent
    platform = (ua.platform or "Device").title()
    browser = (ua.browser or "Browser").title()
    return f"{platform} – {browser}"


# Convert stored UTC iso string -> simple "x min/hr/day ago".
# Used in profile.html Active Sessions list.
def _humanize_utc_iso(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
    except Exception:
        return "Recently"

    delta = datetime.utcnow() - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return "Just now"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"

    days = hours // 24
    return f"{days} day(s) ago"


# Registers (or updates) the current browser/device session under a user's email.
# Called when viewing profile or saving profile.
def register_active_session_for_email(email: str, location: str = "Singapore") -> list[dict]:
    sid = get_or_create_session_id()
    now_iso = datetime.utcnow().isoformat()
    device = _device_label()

    sessions_for_user = ACTIVE_SESSIONS.get(email, [])

    # Update existing record for this session if found
    found = False
    for s in sessions_for_user:
        if s["id"] == sid:
            s["device"] = device
            s["location"] = location
            s["last_seen"] = now_iso
            found = True
            break

    # Otherwise create new session record
    if not found:
        sessions_for_user.append(
            {"id": sid, "device": device, "location": location, "last_seen": now_iso}
        )

    # Keep latest active sessions on top
    sessions_for_user.sort(key=lambda x: x.get("last_seen", ""), reverse=True)
    ACTIVE_SESSIONS[email] = sessions_for_user
    return sessions_for_user


def get_sessions_view(email: str) -> list[dict]:
    """
    Convert raw ACTIVE_SESSIONS into template-friendly objects:
    - adds last_seen_human
    - marks which one is current session
    """
    sid = get_or_create_session_id()
    out = []

    for s in ACTIVE_SESSIONS.get(email, []):
        last_seen = s.get("last_seen", datetime.utcnow().isoformat())
        out.append(
            {
                "id": s.get("id", ""),
                "device": s.get("device", "Device – Browser"),
                "location": s.get("location", "Singapore"),
                "last_seen": last_seen,
                "last_seen_human": _humanize_utc_iso(last_seen),
                "is_current": (s.get("id") == sid),
            }
        )

    return out
