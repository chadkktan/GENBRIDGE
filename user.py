"""
User/session helpers:
- Are we logged in?
- What is the current user's email?
- Load profile into session if it exists in db
- Save profile to db
- Move user/profile records if email changes
"""

from flask import session


# True if the user has an auth_email in Flask session
def is_logged_in() -> bool:
    return bool(session.get("auth_email"))


# Read logged-in email from session.
def current_email() -> str:
    return (session.get("auth_email") or "").strip().lower()


def get_profile_for_current_user(db) -> dict | None:
    """
    Returns the user's profile dict.

    Priority:
    1) If session already has profile, use it.
    2) Otherwise load from db.profiles and put into session.
    """
    prof = session.get("profile")
    if prof:
        return prof

    email = current_email()
    if email and email in db.profiles:
        session["profile"] = db.profiles[email]
        return session["profile"]

    return None


# Save a profile to db.profiles and persist it to profiles.json.
def save_profile_to_store(db, profile: dict) -> None:
    email = (profile.get("email") or "").strip().lower()
    if not email:
        return

    db.profiles[email] = profile
    db.save_profiles()


def move_account_if_email_changed(db, old_email: str, new_email: str) -> tuple[bool, str]:
    """
    If email changes, migrate db.users + db.profiles keys accordingly.
    Returns (ok, message).

    Note: In your current UI, email is mostly readonly in create_profile + profile,
    but this keeps your original backend logic available.
    """
    old_email = (old_email or "").strip().lower()
    new_email = (new_email or "").strip().lower()

    if not old_email or not new_email or old_email == new_email:
        return True, ""

    if new_email in db.users and new_email != old_email:
        return False, "That email is already used by another account."

    if old_email in db.users:
        db.users[new_email] = db.users.pop(old_email)
        db.save_users()

    if old_email in db.profiles:
        db.profiles[new_email] = db.profiles.pop(old_email)
        db.save_profiles()

    # keep session consistent
    session["auth_email"] = new_email

    return True, ""