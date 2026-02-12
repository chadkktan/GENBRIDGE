from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
from functools import wraps
from community_db import increment_members
from community_db import ensure_members_table, join_community_once
from community_db import has_joined, join_community_once, leave_community_once
from config import SECRET_KEY, ensure_dirs

# ✅ JSON DB (users / profiles)
from database import db as json_db
from routes_auth import register_auth_routes
from routes_profile import register_profile_routes

# ✅ Session helpers
from user import is_logged_in, current_email

# ✅ SQLite DB (communities)
from community_db import (
    init_db,
    ensure_created_by_column,
    get_all_communities,
    get_community_by_id,
    create_community,
    update_community,
    delete_community
)

# -----------------------
# App Setup
# -----------------------
app = Flask(__name__)
ensure_dirs()
app.config["SECRET_KEY"] = SECRET_KEY

# ✅ Initialize SQLite + Migration
init_db()
ensure_created_by_column()
ensure_members_table()

# ✅ Register auth / profile routes
register_auth_routes(app, json_db)
register_profile_routes(app, json_db)

# ✅ Categories
CATEGORIES = {
    "exercise": "🚴 Exercise",
    "cooking": "🍳 Cooking",
    "arts_crafts": "🎨 Arts & Crafts",
    "music": "🎶 Music",
    "reading": "📖 Reading",
    "technology": "📱 Technology",
    "wellness": "🏡 Wellness",
}

# -----------------------
# Communities Routes
# -----------------------

def owner_required(view):
    @wraps(view)
    def wrapped(id, *args, **kwargs):
        if not is_logged_in():
            return redirect(url_for("create_account"))

        community = get_community_by_id(id)
        if not community:
            flash("Community not found!", "danger")
            return redirect(url_for("home"))

        if community["created_by_email"] != current_email():
            flash("You are not allowed to edit/delete this community.", "danger")
            return redirect(url_for("home"))

        return view(id, *args, **kwargs)
    return wrapped


@app.route("/home")
def home():
    if not is_logged_in():
        return redirect(url_for("create_account"))

    communities = get_all_communities()
    email = current_email()

    owners = {}
    joined_ids = set()

    for c in communities:
        owner_email = c["created_by_email"]

        if owner_email:
            owners[owner_email] = (
                json_db.profiles.get(owner_email)
                or json_db.users.get(owner_email)
            )

        if email and has_joined(c["id"], email):
            joined_ids.add(c["id"])

    return render_template(
        "landing.html",
        communities=communities,
        categories=CATEGORIES,
        owners=owners,
        joined_ids=joined_ids   # ✅ NEW
    )


@app.route("/create", methods=["GET", "POST"])
def create():
    if not is_logged_in():
        return redirect(url_for("create_account"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        if not name or not category or not description:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("create"))

        owner_email = current_email()  # ✅ From session

        create_community(name, category, description, owner_email)

        flash("Community created successfully!", "success")
        return redirect(url_for("home"))

    return render_template("create.html", categories=CATEGORIES)


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@owner_required
def edit(id):
    community = get_community_by_id(id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        if not name or not category or not description:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("edit", id=id))

        update_community(id, name, category, description)
        flash("Community updated successfully!", "success")
        return redirect(url_for("home"))

    return render_template("edit.html", community=community, categories=CATEGORIES)


@app.route("/delete/<int:id>", methods=["POST"])
@owner_required
def delete(id):
    delete_community(id)
    flash("Community deleted successfully!", "info")
    return redirect(url_for("home"))

@app.route("/community/<int:id>")
def community_view(id):
    if not is_logged_in():
        return redirect(url_for("create_account"))

    community = get_community_by_id(id)
    if not community:
        flash("Community not found!", "danger")
        return redirect(url_for("home"))

    owner_email = community["created_by_email"]
    owner = json_db.profiles.get(owner_email) or json_db.users.get(owner_email)

    return render_template("community_view.html", community=community, owner=owner)

@app.route("/join/<int:id>", methods=["POST"])
def join_community(id):
    if not is_logged_in():
        return redirect(url_for("create_account"))

    email = current_email()

    joined = join_community_once(id, email)

    if joined:
        flash("You joined the community!", "success")
    else:
        flash("You already joined this community.", "info")

    return redirect(url_for("home"))

@app.route("/leave/<int:id>", methods=["POST"])
def leave_community(id):
    if not is_logged_in():
        return redirect(url_for("create_account"))

    email = current_email()

    left = leave_community_once(id, email)

    if left:
        flash("You left the community.", "info")
    else:
        flash("You are not a member of this community.", "warning")

    return redirect(url_for("home"))


@app.context_processor
def inject_datetime():
    return dict(datetime=datetime)


if __name__ == "__main__":
    app.run(debug=True)