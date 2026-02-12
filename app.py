from flask import Flask, render_template, request, redirect, url_for, abort
from werkzeug.utils import secure_filename
import os
import uuid

from Posts import CreatePostForm
from database import DatabaseHelper

db_helper = DatabaseHelper()
app = Flask(__name__)

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


# ---------------- STORIES PAGE ----------------

@app.route('/')
def stories():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "newest")
    mine = int(request.args.get("mine", 0))
    liked = int(request.args.get("liked", 0))

    mine = 1 if mine == 1 else 0
    liked = 1 if liked == 1 else 0

    if q:
        posts_data = db_helper.search_posts_with_tags(q, sort)
    else:
        posts_data = db_helper.get_all_posts_with_tags(sort)

    post_ids = [row[0] for row in posts_data]

    # Add liked_by_me flag (row[6])
    posts_data = [
        row + (1 if db_helper.has_liked(row[0]) else 0,)
        for row in posts_data
    ]

    # If "Liked" filter active
    if liked == 1:
        posts_data = [row for row in posts_data if row[6] == 1]

    comment_preview = db_helper.get_latest_comment_preview_for_posts(post_ids)
    first_images = db_helper.get_first_image_for_posts(post_ids)

    return render_template(
        'stories.html',
        posts_data=posts_data,
        q=q,
        sort=sort,
        liked=liked,
        mine=mine,
        comment_preview=comment_preview,
        first_images=first_images
    )


# ---------------- CREATE POST ----------------

@app.route('/post-creation', methods=['GET', 'POST'])
def post_creation():
    form = CreatePostForm(request.form)

    if request.method == 'POST' and form.validate():
        post_id = db_helper.insert_post(
            form.post_title.data,
            form.post_content.data,
            form.post_tags.data
        )

        files = request.files.getlist("images")
        upload_folder = os.path.join(app.root_path, "static", "uploads")
        saved_filenames = save_uploaded_images(files, upload_folder)

        for name in saved_filenames:
            db_helper.add_post_image(post_id, name)

        return redirect(url_for('stories'))

    return render_template('postCreation.html', form=form)


# ---------------- VIEW POST ----------------

@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = db_helper.get_post_with_tags(post_id)
    comments = db_helper.get_comments_for_post(post_id)
    images = db_helper.get_images_for_post(post_id)

    edit_comment_id = request.args.get("edit_comment_id", "").strip()
    edit_comment_id = int(edit_comment_id) if edit_comment_id.isdigit() else None

    return render_template(
        'postView.html',
        post=post,
        comments=comments,
        images=images,
        edit_comment_id=edit_comment_id
    )


# ---------------- TOGGLE LIKE ----------------

@app.route('/post/<int:post_id>/like', methods=['POST'])
def like_toggle(post_id):
    db_helper.toggle_like(post_id)
    return redirect(request.referrer or url_for('view_post', post_id=post_id))


# ---------------- COMMENTS ----------------

@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    comment_text = request.form.get("comment_text", "").strip()
    db_helper.add_comment(post_id, comment_text)
    return redirect(url_for('view_post', post_id=post_id))


@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    post_id = int(request.form.get("post_id"))
    db_helper.delete_comment(comment_id)
    return redirect(url_for('view_post', post_id=post_id))


@app.route('/comment/<int:comment_id>/edit', methods=['POST'])
def edit_comment(comment_id):
    post_id = int(request.form.get("post_id"))
    new_text = request.form.get("comment_text", "").strip()
    db_helper.update_comment(comment_id, new_text)
    return redirect(url_for('view_post', post_id=post_id))


# ---------------- EDIT POST ----------------

@app.route('/edit-post/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    post = db_helper.get_post_with_tags(post_id)
    form = CreatePostForm(request.form)

    if request.method == 'POST' and form.validate():
        db_helper.update_post(
            post_id,
            form.post_title.data,
            form.post_content.data,
            form.post_tags.data
        )

        files = request.files.getlist("images")
        upload_folder = os.path.join(app.root_path, "static", "uploads")
        saved_filenames = save_uploaded_images(files, upload_folder)

        for name in saved_filenames:
            db_helper.add_post_image(post_id, name)

        return redirect(url_for('view_post', post_id=post_id))

    if request.method == 'GET':
        form.post_title.data = post[1]
        form.post_content.data = post[2]
        form.post_tags.data = post[4]

    images = db_helper.get_images_for_post(post_id)

    return render_template('postCreation.html', form=form, edit=True, images=images)


# ---------------- DELETE POST ----------------

@app.route('/delete-post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    db_helper.delete_post(post_id)
    return redirect(url_for('stories'))


if __name__ == '__main__':
    app.run(debug=True)
