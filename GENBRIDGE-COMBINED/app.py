from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os
import uuid

# -----------------------
# ✅ STORIES / POSTS (SQLite)
# -----------------------
from Posts import CreatePostForm
from post_database import DatabaseHelper

db_helper = DatabaseHelper()

ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_image(filename):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTS


def save_uploaded_images(files, upload_folder):
    os.makedirs(upload_folder, exist_ok=True)
    saved = []

    for f in files:
        if not f or not f.filename:
            continue
        if not allowed_image(f.filename):
            continue

        original = secure_filename(f.filename)
        ext = original.rsplit(".", 1)[1].lower()
        new_name = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(upload_folder, new_name)

        f.save(path)
        saved.append(new_name)

    return saved


# -----------------------
# ✅ COMMUNITIES (JSON auth/profile + SQLite communities)
# -----------------------
from community_db import ensure_members_table, join_community_once, leave_community_once
from community_db import has_joined
from config import SECRET_KEY, ensure_dirs

# ✅ JSON DB (users / profiles)
from database import db as json_db
from routes_auth import register_auth_routes
from routes_profile import register_profile_routes
from routes_events import register_event_routes

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

# ✅ Initialize SQLite + Migration (communities DB)
init_db()
ensure_created_by_column()
ensure_members_table()

# ✅ Register auth / profile routes
register_auth_routes(app, json_db)
register_profile_routes(app, json_db)

# ✅ Register events/booking routes
register_event_routes(app)

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
        joined_ids=joined_ids
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

        owner_email = current_email()
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


# -----------------------
# ✅ STORIES / POSTS Routes (EMAIL-BASED)
# -----------------------

@app.route("/stories")
def stories():
    if not is_logged_in():
        return redirect(url_for("create_account"))

    viewer_email = current_email()

    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "newest")
    mine = 1 if int(request.args.get("mine", 0)) == 1 else 0
    liked = 1 if int(request.args.get("liked", 0)) == 1 else 0

    if q:
        posts_data = db_helper.search_posts_with_tags(q, sort, viewer_email)
    else:
        posts_data = db_helper.get_all_posts_with_tags(sort, viewer_email)

    # ✅ My Posts filter
    if mine == 1:
        posts_data = [row for row in posts_data if (row[4] or "").lower() == viewer_email]

    # ✅ Liked filter (liked_by_me is row[7])
    if liked == 1:
        posts_data = [row for row in posts_data if row[7] == 1]

    post_ids = [row[0] for row in posts_data]
    comment_preview = db_helper.get_latest_comment_preview_for_posts(post_ids)
    first_images = db_helper.get_first_image_for_posts(post_ids)

    return render_template(
        "stories.html",
        posts_data=posts_data,
        q=q,
        sort=sort,
        liked=liked,
        mine=mine,
        comment_preview=comment_preview,
        first_images=first_images,
        current_user_email=viewer_email
    )


@app.route("/post-creation", methods=["GET", "POST"])
def post_creation():
    if not is_logged_in():
        return redirect(url_for("create_account"))

    form = CreatePostForm(request.form)

    if request.method == "POST" and form.validate():
        email = current_email()

        post_id = db_helper.insert_post(
            form.post_title.data,
            form.post_content.data,
            form.post_tags.data,
            email=email
        )

        files = request.files.getlist("images")
        upload_folder = os.path.join(app.root_path, "static", "uploads")
        saved_filenames = save_uploaded_images(files, upload_folder)

        for name in saved_filenames:
            db_helper.add_post_image(post_id, name)

        return redirect(url_for("stories"))

    return render_template("postCreation.html", form=form)


@app.route("/post/<int:post_id>")
def view_post(post_id):
    if not is_logged_in():
        return redirect(url_for("create_account"))

    viewer_email = current_email()
    post = db_helper.get_post_with_tags(post_id, viewer_email)
    comments = db_helper.get_comments_for_post(post_id)
    images = db_helper.get_images_for_post(post_id)

    edit_comment_id = request.args.get("edit_comment_id", "").strip()
    edit_comment_id = int(edit_comment_id) if edit_comment_id.isdigit() else None

    return render_template(
        "postView.html",
        post=post,
        comments=comments,
        images=images,
        edit_comment_id=edit_comment_id,
        current_user_email=viewer_email
    )


@app.route("/post/<int:post_id>/like", methods=["POST"])
def like_toggle(post_id):
    if not is_logged_in():
        return redirect(url_for("create_account"))

    db_helper.toggle_like(post_id, current_email())
    return redirect(request.referrer or url_for("view_post", post_id=post_id))


@app.route("/post/<int:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    if not is_logged_in():
        return redirect(url_for("create_account"))

    comment_text = request.form.get("comment_text", "").strip()
    db_helper.add_comment(post_id, comment_text)
    return redirect(url_for("view_post", post_id=post_id))


@app.route("/comment/<int:comment_id>/delete", methods=["POST"])
def delete_comment(comment_id):
    if not is_logged_in():
        return redirect(url_for("create_account"))

    post_id_raw = request.form.get("post_id")
    if not post_id_raw or not post_id_raw.isdigit():
        return redirect(url_for("stories"))

    post_id = int(post_id_raw)
    db_helper.delete_comment(comment_id)
    return redirect(url_for("view_post", post_id=post_id))


@app.route("/comment/<int:comment_id>/edit", methods=["GET", "POST"])
def edit_comment(comment_id):
    if not is_logged_in():
        return redirect(url_for("create_account"))

    comment = db_helper.get_comment(comment_id)
    if not comment:
        return redirect(url_for("stories"))

    post_id = comment[1]

    if request.method == "POST":
        new_text = request.form.get("comment_text", "").strip()
        if new_text:
            db_helper.update_comment(comment_id, new_text)
        return redirect(url_for("view_post", post_id=post_id))

    return render_template(
        "editComment.html",
        comment=comment,
        post_id=post_id
    )


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    if not is_logged_in():
        return redirect(url_for("create_account"))

    email = current_email()

    # ✅ Only owner can edit
    if not db_helper.post_belongs_to_email(post_id, email):
        flash("You are not allowed to edit this post.", "danger")
        return redirect(url_for("stories"))

    post = db_helper.get_post_with_tags(post_id, email)
    if not post:
        return redirect(url_for("stories"))

    form = CreatePostForm(request.form)

    if request.method == "POST" and form.validate():
        db_helper.update_post(
            post_id,
            form.post_title.data,
            form.post_content.data,
            form.post_tags.data
        )

        remove_ids = request.form.getlist("remove_image_ids")
        upload_folder = os.path.join(app.root_path, "static", "uploads")

        for rid in remove_ids:
            try:
                image_id = int(rid)
            except ValueError:
                continue

            img = db_helper.get_post_image(image_id)
            if not img:
                continue

            if img[1] != post_id:
                continue

            filename = img[2]
            db_helper.delete_post_image(image_id)

            file_path = os.path.join(upload_folder, filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        files = request.files.getlist("images")
        saved_filenames = save_uploaded_images(files, upload_folder)

        for name in saved_filenames:
            db_helper.add_post_image(post_id, name)

        return redirect(url_for("stories"))

    if request.method == "GET":
        form.post_title.data = post[1]
        form.post_content.data = post[2]
        form.post_tags.data = post[5]  # tags

    images = db_helper.get_images_for_post(post_id)
    return render_template("postCreation.html", form=form, edit=True, images=images)


@app.route("/delete-post/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    if not is_logged_in():
        return redirect(url_for("create_account"))

    email = current_email()

    # ✅ Only owner can delete
    if not db_helper.post_belongs_to_email(post_id, email):
        flash("You are not allowed to delete this post.", "danger")
        return redirect(url_for("stories"))

    db_helper.delete_post(post_id)
    return redirect(url_for("stories"))


# -----------------------
# Context
# -----------------------
@app.context_processor
def inject_datetime():
    return dict(datetime=datetime)


if __name__ == "__main__":
    app.run(debug=True)
