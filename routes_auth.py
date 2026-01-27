"""
All authentication/account routes:
- /
- /create-account
- /sign-in
- /sign-out
- /delete-account
"""

from datetime import datetime

from flask import render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from sessions import get_or_create_session_id, ACTIVE_SESSIONS
from user import is_logged_in, current_email, get_profile_for_current_user
from validators import validate_email_com


def register_auth_routes(app, db) -> None:
    """
    Attach auth-related routes to the Flask app.
    """

    def index():
        """
        - If logged in and profile exists -> /profile
        - If logged in but no profile -> /create-profile
        - If not logged in -> /create-account
        """
        if is_logged_in():
            prof = get_profile_for_current_user(db)
            if prof and prof.get("first_name"):
                return redirect(url_for("profile"))
            return redirect(url_for("create_profile"))
        return redirect(url_for("create_account"))

    def create_account():
        """
        GET: render create_account.html
        POST: validate + create user in users.json + login + redirect to create profile
        """
        if request.method == "POST":
            full_name = (request.form.get("full_name") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            pw = request.form.get("password") or ""
            cpw = request.form.get("confirm_password") or ""
            terms = request.form.get("terms")

            errors = []
            open_signin = False

            if not full_name:
                errors.append("Full name is required.")

            # .com-only rule for create account
            if not email or not validate_email_com(email):
                errors.append("Email must look like xxx@xxx.com")

            if not pw:
                errors.append("Password is required.")

            if pw != cpw:
                errors.append("Passwords do not match.")

            if not terms:
                errors.append("You must agree to the Terms of Service and Privacy Policy.")

            if email and email in db.users:
                errors.append("Email already has an account")
                open_signin = True

            if errors:
                for e in errors:
                    flash(e, "error")

                # tells template to auto-open sign-in modal
                if open_signin:
                    return redirect(url_for("create_account", show_signin="1"))

                return redirect(url_for("create_account"))

            # Create new user record
            db.users[email] = {
                "full_name": full_name,
                "pw_hash": generate_password_hash(pw),
                "created_at": datetime.utcnow().isoformat(),
            }
            db.save_users()

            # Log them in
            session.clear()
            session["auth_email"] = email
            session["auth_name"] = full_name
            get_or_create_session_id()

            # prefill profile email
            session["profile"] = {"email": email}

            flash("Account created successfully.", "success")
            return redirect(url_for("create_profile"))

        show_signin = request.args.get("show_signin") == "1"
        return render_template("create_account.html", show_signin=show_signin)

    def sign_in():
        """
        POST: validate password against db.users and login.
        GET: redirect back to create-account with sign-in modal open.
        """
        if request.method == "GET":
            return redirect(url_for("create_account", show_signin="1"))

        email = (request.form.get("email") or "").strip().lower()
        pw = (request.form.get("password") or "")

        if not email or not pw:
            flash("Please enter your email and password.", "signin_error")
            return redirect(url_for("create_account", show_signin="1"))

        user = db.users.get(email)
        if not user or not check_password_hash(user.get("pw_hash", ""), pw):
            flash("Invalid email or password.", "signin_error")
            return redirect(url_for("create_account", show_signin="1"))

        session.clear()
        session["auth_email"] = email
        session["auth_name"] = user.get("full_name", "")
        get_or_create_session_id()

        # If profile exists, go straight to profile page
        if email in db.profiles and db.profiles[email].get("first_name"):
            session["profile"] = db.profiles[email]
            return redirect(url_for("profile"))

        # Otherwise go to create profile wizard
        session["profile"] = {"email": email}
        return redirect(url_for("create_profile"))

    def sign_out():
        """
        Remove current session from ACTIVE_SESSIONS list, then clear session cookie.
        """
        prof = session.get("profile") or {}
        email = (prof.get("email") or "").strip().lower()
        sid = session.get("session_id")

        if email and sid and email in ACTIVE_SESSIONS:
            ACTIVE_SESSIONS[email] = [s for s in ACTIVE_SESSIONS[email] if s.get("id") != sid]

        session.clear()
        return redirect(url_for("create_account", msg="signed_out"))

    def delete_account():
        """
        Deletes user + profile from JSON files and clears active sessions.
        """
        email = current_email()

        if email:
            db.users.pop(email, None)
            db.profiles.pop(email, None)
            ACTIVE_SESSIONS.pop(email, None)

            db.save_users()
            db.save_profiles()

        session.clear()
        return redirect(url_for("create_account", msg="deleted"))

    # Register routes (keep exact URLs/endpoints)
    app.add_url_rule("/", endpoint="index", view_func=index, methods=["GET"])
    app.add_url_rule("/create-account", endpoint="create_account", view_func=create_account, methods=["GET", "POST"])
    app.add_url_rule("/sign-in", endpoint="sign_in", view_func=sign_in, methods=["GET", "POST"])
    app.add_url_rule("/sign-out", endpoint="sign_out", view_func=sign_out, methods=["GET"])
    app.add_url_rule("/delete-account", endpoint="delete_account", view_func=delete_account, methods=["GET"])
