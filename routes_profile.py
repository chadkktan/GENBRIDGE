"""
All profile-related routes:
- /create-profile (wizard page)
- /save-profile   (submit wizard)
- /profile        (profile page)
- /update-profile (edit profile)
- /revoke-session (AJAX revoke session)
- /restart-profile (start over)

Also handles avatar upload logic (saving into static/uploads).
"""

import os
from datetime import datetime

from flask import render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename

from config import UPLOAD_FOLDER
from sessions import (
    get_or_create_session_id,
    register_active_session_for_email,
    get_sessions_view,
    ACTIVE_SESSIONS,
)
from user import (
    is_logged_in,
    current_email,
    get_profile_for_current_user,
    save_profile_to_store,
    move_account_if_email_changed,
)
from validators import allowed_file, validate_email, validate_phone, get_interests_from_request


# Attach profile-related routes to the Flask app.
def register_profile_routes(app, db) -> None:

    def create_profile():
        """
        Render wizard page.
        Ensures we have a session profile dict with email prefilled.
        """
        if not is_logged_in():
            return redirect(url_for("create_account"))

        existing = get_profile_for_current_user(db)
        if not existing:
            existing = {"email": current_email()}
            session["profile"] = existing

        if not existing.get("email"):
            existing["email"] = current_email()
            session["profile"] = existing

        return render_template("create_profile.html", profile=existing)

    def save_profile():
        """
        Handles wizard POST:
        - validate fields
        - save avatar
        - save profile to session + profiles.json
        - register active session record
        """
        if not is_logged_in():
            return redirect(url_for("create_account"))

        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        dob = (request.form.get("dob") or "").strip()
        location = (request.form.get("location") or "").strip()

        # Force email to always be the logged in email 
        auth_email = current_email()
        if auth_email:
            email = auth_email

        role = (request.form.get("role") or "").strip()
        interests = get_interests_from_request(request)

        bio = (request.form.get("bio") or "").strip()
        website = (request.form.get("website") or "").strip() or "-"

        avatar_filename = None
        file = request.files.get("avatar")

        errors = []

        # Basic validations 
        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if not email or not validate_email(email):
            errors.append("Please enter a valid email address.")
        if not phone or not validate_phone(phone):
            errors.append("Phone number is invalid.")

        if not dob:
            errors.append("Date of birth is required.")
        else:
            try:
                datetime.strptime(dob, "%Y-%m-%d")
            except ValueError:
                errors.append("Date of birth is invalid.")

        if not location:
            errors.append("Location is required.")

        if role not in {"Young Person", "Senior"}:
            errors.append("Please select whether you are a Young Person or Senior.")

        if len(interests) < 3:
            errors.append("Please select at least 3 interests.")

        if len(bio) > 500:
            errors.append("Bio must be 500 characters or less.")

        # Avatar upload
        if file and file.filename:
            if not allowed_file(file.filename):
                errors.append("Avatar must be an image file (png/jpg/jpeg/webp/gif).")
            else:
                safe_name = secure_filename(file.filename)
                stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
                avatar_filename = f"{stamp}_{safe_name}"
                file.save(os.path.join(UPLOAD_FOLDER, avatar_filename))

        # If errors: flash + keep user input in session then redirect back
        if errors:
            for e in errors:
                flash(e, "error")

            session["profile"] = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "dob": dob,
                "location": location,
                "website": website,
                "bio": bio,
                "role": role,
                "interests": interests,
                "avatar_filename": session.get("profile", {}).get("avatar_filename"),
            }

            return redirect(url_for("create_profile"))

        # If user didn't upload a new avatar now, keep the old one (if exists)
        if not avatar_filename:
            avatar_filename = session.get("profile", {}).get("avatar_filename")

        new_profile = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "dob": dob,
            "location": location,
            "website": website,
            "bio": bio,
            "role": role,
            "interests": interests,
            "avatar_filename": avatar_filename,
        }

        # Save into session + JSON file
        session["profile"] = new_profile
        save_profile_to_store(db, new_profile)

        # Track active sessions in memory
        if email:
            register_active_session_for_email(email, location)

        return redirect(url_for("profile"))

    def profile():
        """
        Render the profile page.
        Also updates active session "last seen".
        """
        if not is_logged_in():
            return redirect(url_for("create_account"))

        prof = get_profile_for_current_user(db)
        if not prof or not prof.get("first_name"):
            return redirect(url_for("create_profile"))

        email = (prof.get("email") or "").strip().lower()
        location = prof.get("location", "Singapore")

        if email:
            register_active_session_for_email(email, location)

        active_sessions = get_sessions_view(email) if email else []
        return render_template("profile.html", profile=prof, active_sessions=active_sessions)

    def update_profile():
        """
        Handles POST from profile edit form.
        Updates allowed fields + avatar.
        """
        if not is_logged_in():
            return redirect(url_for("create_account"))

        prof = get_profile_for_current_user(db)
        if not prof:
            return redirect(url_for("create_profile"))

        old_email = (prof.get("email") or "").strip().lower()

        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()

        # Force email = logged in email 
        email = current_email()

        phone = (request.form.get("phone") or "").strip()
        location = (request.form.get("location") or "").strip()
        website = (request.form.get("website") or "").strip() or "-"
        bio = (request.form.get("bio") or "").strip()

        avatar_filename = prof.get("avatar_filename")
        file = request.files.get("avatar")

        errors = []

        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if not email or not validate_email(email):
            errors.append("Please enter a valid email address.")
        if not phone or not validate_phone(phone):
            errors.append("Phone number is invalid.")
        if len(bio) > 500:
            errors.append("Bio must be 500 characters or less.")

        if file and file.filename:
            if not allowed_file(file.filename):
                errors.append("Avatar must be an image file (png/jpg/jpeg/webp/gif).")
            else:
                safe_name = secure_filename(file.filename)
                stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
                avatar_filename = f"{stamp}_{safe_name}"
                file.save(os.path.join(UPLOAD_FOLDER, avatar_filename))

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("profile"))

        # Update profile object
        prof.update(
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "location": location,
                "website": website,
                "bio": bio,
                "avatar_filename": avatar_filename,
            }
        )

        session["profile"] = prof
        save_profile_to_store(db, prof)

        # If email changed, move keys in JSON + also move active sessions list
        if old_email and old_email != email:
            ok, msg = move_account_if_email_changed(db, old_email, email)
            if not ok:
                flash(msg, "error")
                return redirect(url_for("profile"))

            if old_email in ACTIVE_SESSIONS:
                ACTIVE_SESSIONS[email] = ACTIVE_SESSIONS.pop(old_email)

        if email:
            register_active_session_for_email(email, location)

        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    def revoke_session():
        """
        AJAX endpoint called by profile.html when user clicks "Revoke".
        Removes that session record from ACTIVE_SESSIONS.
        If revoking current session -> clear cookie and redirect to create-account.
        """
        prof = get_profile_for_current_user(db)
        if not prof:
            return {"ok": False, "message": "Not logged in."}, 401

        email = (prof.get("email") or "").strip().lower()
        if not email:
            return {"ok": False, "message": "No profile email."}, 400

        data = request.get_json(silent=True) or {}
        sid = (data.get("session_id") or "").strip()
        if not sid:
            return {"ok": False, "message": "Missing session_id."}, 400

        sessions_for_user = ACTIVE_SESSIONS.get(email, [])
        before = len(sessions_for_user)

        sessions_for_user = [s for s in sessions_for_user if s.get("id") != sid]
        ACTIVE_SESSIONS[email] = sessions_for_user

        current_sid = get_or_create_session_id()

        # If they revoked themselves, force sign-out
        if sid == current_sid:
            session.clear()
            return {"ok": True, "revoked_current": True, "redirect": url_for("create_account")}

        return {
            "ok": True,
            "removed": (before != len(sessions_for_user)),
            "revoked_current": False,
        }

    def restart_profile():
        """
        Clears profile data for current user, deletes their profile from profiles.json,
        and returns them to the create-profile wizard.
        """
        prof = session.get("profile") or {}
        email = (prof.get("email") or "").strip().lower() or current_email()

        session["profile"] = {"email": email} if email else {}

        if email and email in db.profiles:
            db.profiles.pop(email, None)
            db.save_profiles()

        return redirect(url_for("create_profile"))

    # Register routes (keep exact URLs/endpoints)
    app.add_url_rule("/create-profile", endpoint="create_profile", view_func=create_profile, methods=["GET"])
    app.add_url_rule("/save-profile", endpoint="save_profile", view_func=save_profile, methods=["POST"])
    app.add_url_rule("/profile", endpoint="profile", view_func=profile, methods=["GET"])
    app.add_url_rule("/update-profile", endpoint="update_profile", view_func=update_profile, methods=["POST"])
    app.add_url_rule("/revoke-session", endpoint="revoke_session", view_func=revoke_session, methods=["POST"])
    app.add_url_rule("/restart-profile", endpoint="restart_profile", view_func=restart_profile, methods=["GET"])
