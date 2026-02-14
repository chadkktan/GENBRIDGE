from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os
import uuid
from flask_socketio import SocketIO
from services import (
    get_db,
    get_media_db,
    init_db,
    init_media_db,
    register_socket_events
)

from auth import (
    get_current_user_from_session,
    get_user_by_id,
    search_users,
    require_login
)

from community_db import (
    get_community_by_id,
    init_db as init_community_db,
    ensure_members_table
)

from config import SECRET_KEY, ensure_dirs

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
socketio = SocketIO(app, cors_allowed_origins="*")

ensure_dirs()
init_db()
init_media_db()
init_community_db()
ensure_members_table()
register_socket_events(socketio)


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
# -------------------------
# API: Search Users (for adding chats)
# -------------------------
@app.route("/api/users/search", methods=["GET"])
@require_login
def search_users_api():
    """Search for users to start a chat with"""
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return jsonify({
            "status": "error",
            "message": "Query must be at least 2 characters"
        }), 400
    
    current_user = get_current_user()
    results = search_users(query)
    
    # Filter out current user from results
    results = [u for u in results if u['user_id'] != current_user['user_id']]
    
    return jsonify({
        "status": "success",
        "users": results
    }), 200

# -------------------------
# API: Chats (Private)
# -------------------------
@app.route("/api/chats", methods=["POST"])
@require_login
def create_chat():
    """Create a new PRIVATE chat between current user and another user"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400

        # Get the other user's ID
        other_user_id = data.get("user_id")
        
        if not other_user_id:
            return jsonify({
                "status": "error", 
                "message": "User ID is required"
            }), 400

        # Verify the other user exists
        other_user = get_user_by_id(other_user_id)
        if not other_user:
            return jsonify({
                "status": "error", 
                "message": "User not found"
            }), 404

        # Get nickname from their user data
        nickname = other_user.get('name', other_user_id)

        conn = get_db()
        cursor = conn.cursor()

        # Check if private chat already exists between these two users
        cursor.execute("""
            SELECT id FROM chats 
            WHERE (user_id = ? AND creator_id = ?) 
               OR (user_id = ? AND creator_id = ?)
        """, (other_user_id, current_user['user_id'], 
              current_user['user_id'], other_user_id))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            print(f"⚠️  Private chat already exists between {current_user['user_id']} and {other_user_id}")
            return jsonify({
                "status": "error", 
                "message": "Chat already exists",
                "chat_id": existing["id"]
            }), 409

        # Insert new PRIVATE chat
        cursor.execute("""
            INSERT INTO chats (user_id, nickname, creator_id, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (other_user_id, nickname, current_user['user_id']))

        conn.commit()
        chat_id = cursor.lastrowid
        conn.close()

        print(f"✅ Private chat created: {nickname} (Chat ID: {chat_id})")
        print(f"   Participants: {current_user['user_id']} ↔️ {other_user_id}")

        chat_data = {
            "chat_id": chat_id,
            "user_id": other_user_id,
            "nickname": nickname,
            "creator_id": current_user['user_id'],
            "last_message": "",
            "last_message_time": None,
            "created_at": datetime.now().isoformat()
        }
        socketio.emit('chat_created', chat_data, namespace='/')

        return jsonify({
            "status": "success", 
            "chat_id": chat_id, 
            "user_id": other_user_id,
            "nickname": nickname
        }), 201

    except Exception as e:
        print(f"❌ Error creating chat: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500

@app.route("/api/chats", methods=["GET"])
@require_login
def get_chats():
    """Get all PRIVATE chats for current user"""
    try:
        current_user = get_current_user()
        user_id = current_user['user_id']
        
        print(f"📋 GET /api/chats called for user: {user_id}")
        conn = get_db()
        cursor = conn.cursor()

        # Get chats where user is EITHER creator OR recipient
        cursor.execute("""
            SELECT 
                c.id AS chat_id, 
                c.user_id, 
                c.nickname,
                c.creator_id,
                c.created_at,
                (
                    SELECT m.content 
                    FROM messages m 
                    WHERE m.chat_id = c.id 
                    ORDER BY m.timestamp DESC 
                    LIMIT 1
                ) AS last_message,
                (
                    SELECT m.timestamp 
                    FROM messages m 
                    WHERE m.chat_id = c.id 
                    ORDER BY m.timestamp DESC 
                    LIMIT 1
                ) AS last_message_time
            FROM chats c
            WHERE c.user_id = ? OR c.creator_id = ?
            ORDER BY 
                CASE 
                    WHEN last_message_time IS NULL THEN c.created_at 
                    ELSE last_message_time 
                END DESC
        """, (user_id, user_id))
        
        rows = cursor.fetchall()
        conn.close()

        chats = []
        for row in rows:
            chats.append({
                "chat_id": row["chat_id"],
                "user_id": row["user_id"],
                "nickname": row["nickname"],
                "creator_id": row["creator_id"],
                "last_message": row["last_message"] or "",
                "last_message_time": row["last_message_time"],
                "created_at": row["created_at"]
            })

        print(f"📋 Returned {len(chats)} private chats for {user_id}")
        return jsonify({"status": "success", "chats": chats}), 200

    except Exception as e:
        print(f"❌ Error getting chats: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500

@app.route("/api/chats/<int:chat_id>", methods=["DELETE"])
@require_login
def delete_chat(chat_id):
    """Delete a chat and all its messages"""
    try:
        current_user = get_current_user()
        conn = get_db()
        cursor = conn.cursor()

        # Verify user is a participant in this chat
        cursor.execute("""
            SELECT id, nickname, creator_id, user_id 
            FROM chats 
            WHERE id = ? AND (creator_id = ? OR user_id = ?)
        """, (chat_id, current_user['user_id'], current_user['user_id']))
        
        chat = cursor.fetchone()
        if not chat:
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "Chat not found or access denied"
            }), 404

        # Delete all messages
        cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        
        # Delete media files associated with this chat
        media_conn = get_media_db()
        media_cursor = media_conn.cursor()
        media_cursor.execute("DELETE FROM media WHERE chat_id = ?", (chat_id,))
        media_conn.commit()
        media_conn.close()
        
        # Delete chat
        cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        
        conn.commit()
        conn.close()

        print(f"🗑️  Chat deleted: {chat['nickname']} (Chat ID: {chat_id})")

        socketio.emit('chat_deleted', {"chat_id": chat_id}, namespace='/')

        return jsonify({"status": "success", "message": "Chat deleted"}), 200

    except Exception as e:
        print(f"❌ Error deleting chat: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500

# -------------------------
# API: Messages
# -------------------------
@app.route("/api/messages/send", methods=["POST"])
@require_login
def send_message():
    """Send a text message"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400

        chat_id = data.get("chat_id")
        content = data.get("content", "").strip()

        if not chat_id:
            return jsonify({
                "status": "error", 
                "message": "Chat ID is required"
            }), 400

        if not content:
            return jsonify({
                "status": "error", 
                "message": "Message content is required"
            }), 400

        conn = get_db()
        cursor = conn.cursor()

        # Verify user is participant in this chat
        cursor.execute("""
            SELECT nickname, user_id, creator_id 
            FROM chats 
            WHERE id = ? AND (user_id = ? OR creator_id = ?)
        """, (chat_id, current_user['user_id'], current_user['user_id']))
        
        chat = cursor.fetchone()
        if not chat:
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "Chat not found or access denied"
            }), 404

        # Insert message
        cursor.execute("""
            INSERT INTO messages (chat_id, sender_id, content, timestamp)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (chat_id, current_user['user_id'], content))

        conn.commit()
        message_id = cursor.lastrowid
        
        cursor.execute("SELECT timestamp FROM messages WHERE id = ?", (message_id,))
        timestamp = cursor.fetchone()['timestamp']
        conn.close()

        # Determine recipient
        recipient_id = chat['user_id'] if current_user['user_id'] == chat['creator_id'] else chat['creator_id']
        recipient_name = chat['nickname']
        
        print(f"💬 Message sent in Chat {chat_id}:")
        print(f"   From: {current_user['name']} ({current_user['user_id']}) → To: {recipient_name} ({recipient_id})")
        print(f"   Message ID: {message_id}")
        print(f"   Content: \"{content}\"")

        message_data = {
            "message_id": message_id,
            "chat_id": chat_id,
            "sender_id": current_user['user_id'],
            "content": content,
            "media_url": None,
            "media_type": None,
            "timestamp": timestamp
        }
        socketio.emit('new_message', message_data, namespace='/')

        return jsonify({
            "status": "success", 
            "message_id": message_id
        }), 201

    except Exception as e:
        print(f"❌ Error sending message: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500

@app.route("/api/media/upload", methods=["POST"])
@require_login
def upload_media():
    """Upload media file to separate database"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        chat_id = data.get("chat_id")
        filename = data.get("filename")
        file_data = data.get("data")  # Base64
        mime_type = data.get("mime_type")

        if not all([chat_id, filename, file_data, mime_type]):
            return jsonify({
                "status": "error", 
                "message": "Missing required fields"
            }), 400

        conn = get_db()
        cursor = conn.cursor()

        # Verify user is participant
        cursor.execute("""
            SELECT nickname, user_id, creator_id 
            FROM chats 
            WHERE id = ? AND (user_id = ? OR creator_id = ?)
        """, (chat_id, current_user['user_id'], current_user['user_id']))
        
        chat = cursor.fetchone()
        if not chat:
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "Chat not found or access denied"
            }), 404

        # Save to media database
        media_conn = get_media_db()
        media_cursor = media_conn.cursor()

        media_cursor.execute("""
            INSERT INTO media (chat_id, sender_id, filename, data, mime_type, uploaded_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (chat_id, current_user['user_id'], filename, file_data, mime_type))

        media_conn.commit()
        media_id = media_cursor.lastrowid
        media_conn.close()

        content = f"Shared {mime_type.split('/')[0]}: {filename}"
        
        cursor.execute("""
            INSERT INTO messages (chat_id, sender_id, content, media_id, timestamp)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (chat_id, current_user['user_id'], content, media_id))

        conn.commit()
        message_id = cursor.lastrowid
        
        cursor.execute("SELECT timestamp FROM messages WHERE id = ?", (message_id,))
        timestamp = cursor.fetchone()['timestamp']
        conn.close()

        recipient_id = chat['user_id'] if current_user['user_id'] == chat['creator_id'] else chat['creator_id']
        recipient_name = chat['nickname']
        
        print(f"💬 Media message sent in Chat {chat_id}:")
        print(f"   From: {current_user['name']} ({current_user['user_id']}) → To: {recipient_name} ({recipient_id})")
        print(f"   Message ID: {message_id}, Media ID: {media_id}")
        print(f"   File: {filename} ({mime_type})")

        message_data = {
            "message_id": message_id,
            "chat_id": chat_id,
            "sender_id": current_user['user_id'],
            "content": content,
            "media_url": file_data,
            "media_type": mime_type,
            "timestamp": timestamp
        }
        socketio.emit('new_message', message_data, namespace='/')

        return jsonify({
            "status": "success", 
            "message_id": message_id,
            "media_id": media_id
        }), 201

    except Exception as e:
        print(f"❌ Error uploading media: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500

@app.route("/api/messages/<int:message_id>", methods=["PUT"])
@require_login
def edit_message(message_id):
    """Edit a message (only if you're the sender)"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400

        content = data.get("content", "").strip()

        if not content:
            return jsonify({
                "status": "error", 
                "message": "Message content is required"
            }), 400

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT chat_id, sender_id 
            FROM messages 
            WHERE id = ?
        """, (message_id,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "Message not found"
            }), 404

        # Verify user is the sender
        if result['sender_id'] != current_user['user_id']:
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "You can only edit your own messages"
            }), 403

        chat_id = result['chat_id']

        cursor.execute("UPDATE messages SET content = ? WHERE id = ?", (content, message_id))

        conn.commit()
        conn.close()

        print(f"✏️  Message edited:")
        print(f"   Message ID: {message_id} in Chat {chat_id}")
        print(f"   Sender: {current_user['name']} ({current_user['user_id']})")
        print(f"   New content: \"{content}\"")

        socketio.emit('message_edited', {
            "message_id": message_id,
            "chat_id": chat_id,
            "content": content
        }, namespace='/')

        return jsonify({
            "status": "success", 
            "message_id": message_id
        }), 200

    except Exception as e:
        print(f"❌ Error editing message: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500

@app.route("/api/messages/<int:message_id>", methods=["DELETE"])
@require_login
def delete_message(message_id):
    """Delete a message (only if you're the sender)"""
    try:
        current_user = get_current_user()
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT chat_id, sender_id, content, media_id 
            FROM messages 
            WHERE id = ?
        """, (message_id,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "Message not found"
            }), 404

        # Verify user is the sender
        if result['sender_id'] != current_user['user_id']:
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "You can only delete your own messages"
            }), 403

        chat_id = result['chat_id']
        content = result['content']
        media_id = result['media_id']

        # Delete associated media if exists
        if media_id:
            media_conn = get_media_db()
            media_cursor = media_conn.cursor()
            media_cursor.execute("DELETE FROM media WHERE id = ?", (media_id,))
            media_conn.commit()
            media_conn.close()

        cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        conn.commit()

        # Get the NEW last message for this chat
        cursor.execute("""
            SELECT content, timestamp 
            FROM messages 
            WHERE chat_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (chat_id,))
        
        last_msg = cursor.fetchone()
        new_last_message = last_msg['content'] if last_msg else ""
        
        conn.close()

        print(f"🗑️  Message deleted:")
        print(f"   Message ID: {message_id} from Chat {chat_id}")
        print(f"   Sender: {current_user['name']} ({current_user['user_id']})")
        print(f"   Content: \"{content}\"")
        print(f"   New last message: \"{new_last_message}\"")

        socketio.emit('message_deleted', {
            "message_id": message_id,
            "chat_id": chat_id,
            "new_last_message": new_last_message
        }, namespace='/')

        return jsonify({
            "status": "success", 
            "message": "Message deleted",
            "new_last_message": new_last_message
        }), 200

    except Exception as e:
        print(f"❌ Error deleting message: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500

@app.route("/api/messages/<int:chat_id>", methods=["GET"])
@require_login
def get_messages(chat_id):
    """Get all messages for a specific chat"""
    try:
        current_user = get_current_user()
        conn = get_db()
        cursor = conn.cursor()

        # Verify user is participant
        cursor.execute("""
            SELECT id, nickname 
            FROM chats 
            WHERE id = ? AND (user_id = ? OR creator_id = ?)
        """, (chat_id, current_user['user_id'], current_user['user_id']))
        
        chat = cursor.fetchone()
        if not chat:
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "Chat not found or access denied"
            }), 404

        # Get messages
        cursor.execute("""
            SELECT id as message_id, sender_id, content, media_id, timestamp
            FROM messages
            WHERE chat_id = ?
            ORDER BY timestamp ASC
        """, (chat_id,))

        messages = cursor.fetchall()
        conn.close()

        # Get media data for messages with media
        media_conn = get_media_db()
        media_cursor = media_conn.cursor()

        result_messages = []
        for msg in messages:
            msg_dict = dict(msg)
            
            if msg['media_id']:
                media_cursor.execute("""
                    SELECT data, mime_type FROM media WHERE id = ?
                """, (msg['media_id'],))
                media = media_cursor.fetchone()
                
                if media:
                    msg_dict['media_url'] = media['data']
                    msg_dict['media_type'] = media['mime_type']
                else:
                    msg_dict['media_url'] = None
                    msg_dict['media_type'] = None
            else:
                msg_dict['media_url'] = None
                msg_dict['media_type'] = None
            
            result_messages.append(msg_dict)

        media_conn.close()

        print(f"📨 Retrieved {len(result_messages)} messages from Chat {chat_id} ({chat['nickname']})")

        return jsonify({
            "status": "success",
            "messages": result_messages
        }), 200

    except Exception as e:
        print(f"❌ Error getting messages: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500


#-------------------------
#Community routes  
#-------------------------
@app.route('/community/post')
def community_post():
    return render_template('community.html')

@app.route('/api/post/<post_id>')
def get_post(post_id):
    try:
        community = get_community_by_id(int(post_id))
        if not community:
            return jsonify({"error": "Not found"}), 404
        
        c = dict(community)
        
        return jsonify({
            "community": {
                "name": c['name'],
                
            },
            "post": {
                "title": c['name'],
                "description": c['description'],
                "content": c['description'],
                "author": {
                    "username": c.get('created_by_email', 'Admin').split('@')[0],
                    "avatar": c.get('created_by_email', '?')[0].upper()
                },
                "timestamp": "Recently"
            },
            "comments": []
        })
    except:
        return jsonify({"error": "Error"}), 500

# -----------------------
# Context
# -----------------------
@app.context_processor
def inject_datetime():
    return dict(datetime=datetime)


if __name__ == "__main__":
    app.run(debug=True)
