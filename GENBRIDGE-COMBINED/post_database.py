import sqlite3


class DatabaseHelper:
    """
    Updated to use session email as the "user id" for:
    - post ownership (posts.email)
    - likes (post_likes.user_email)
    - liked_by_me flag in queries

    IMPORTANT:
    - This version creates post_likes with user_email (TEXT) instead of user_id (INTEGER).
    - If you already have the old post_likes table, see migrate_post_likes_table() below.
    """

    def __init__(self, db_name="post_info"):
        self.db_name = db_name
        self.init_database()

    def _connect(self):
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_database(self):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_title TEXT NOT NULL,
                post_content TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT NOT NULL UNIQUE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_tags (
                post_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (post_id, tag_id),
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                comment_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_images (
                image_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            )
        """)

        # ✅ UPDATED: likes tied to user_email (not user_id)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_likes (
                like_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, user_email),
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            )
        """)

        conn.commit()
        conn.close()

    # ---------------- OPTIONAL MIGRATION ----------------
    def migrate_post_likes_table(self):
        """
        Run this ONCE if you previously created post_likes(post_id, user_id).
        This drops old likes because user_id can't be mapped to email safely.
        """
        conn = self._connect()
        cur = conn.cursor()

        # check columns
        cur.execute("PRAGMA table_info(post_likes)")
        cols = [r[1] for r in cur.fetchall()]  # column names

        # If already migrated, do nothing
        if "user_email" in cols:
            conn.close()
            return

        # Otherwise rebuild
        cur.execute("ALTER TABLE post_likes RENAME TO post_likes_old")

        cur.execute("""
            CREATE TABLE post_likes (
                like_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, user_email),
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            )
        """)

        # drop old data (cannot map user_id -> email)
        cur.execute("DROP TABLE post_likes_old")
        conn.commit()
        conn.close()

    # ---------------- HELPERS ----------------

    def normalize_email(self, email):
        return (email or "").strip().lower()

    def normalize_tags(self, raw_tags):
        if raw_tags is None:
            return []

        split_tags = [t.strip().lower() for t in str(raw_tags).split(",")]

        filled_tags_holder = []
        for t in split_tags:
            if t != "":
                filled_tags_holder.append(t)

        seen = set()
        cleaned_tags = []
        for t in filled_tags_holder:
            if t not in seen:
                seen.add(t)
                cleaned_tags.append(t)

        return cleaned_tags

    def post_belongs_to_email(self, post_id, email):
        email = self.normalize_email(email)
        if not email:
            return False

        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM posts WHERE post_id = ? AND email = ? LIMIT 1",
            (post_id, email),
        )
        ok = cur.fetchone() is not None
        conn.close()
        return ok

    # ---------------- POSTS ----------------

    def insert_post(self, post_title, post_content, post_tags, email):
        email = self.normalize_email(email)

        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO posts (post_title, post_content, email, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (post_title, post_content, email))

        post_id = cursor.lastrowid

        tags = self.normalize_tags(post_tags)
        for tag in tags:
            cursor.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES (?)", (tag,))
            cursor.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (tag,))
            tag_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT OR IGNORE INTO post_tags (post_id, tag_id) VALUES (?, ?)",
                (post_id, tag_id),
            )

        conn.commit()
        conn.close()
        return post_id

    def update_post(self, post_id, title, content, tags):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE posts
            SET post_title = ?, post_content = ?
            WHERE post_id = ?
        """, (title, content, post_id))

        cursor.execute("DELETE FROM post_tags WHERE post_id = ?", (post_id,))

        cleaned = self.normalize_tags(tags)
        for t in cleaned:
            cursor.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES (?)", (t,))
            cursor.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (t,))
            tag_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT OR IGNORE INTO post_tags (post_id, tag_id)
                VALUES (?, ?)
            """, (post_id, tag_id))

        conn.commit()
        conn.close()

    def delete_post(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))
        conn.commit()
        conn.close()

    # ---------------- LIKES (BY EMAIL) ----------------

    def like_post(self, post_id, user_email):
        user_email = self.normalize_email(user_email)
        if not user_email:
            return False

        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO post_likes (post_id, user_email, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (post_id, user_email))
        conn.commit()
        conn.close()
        return True

    def unlike_post(self, post_id, user_email):
        user_email = self.normalize_email(user_email)
        if not user_email:
            return False

        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM post_likes
            WHERE post_id = ? AND user_email = ?
        """, (post_id, user_email))
        conn.commit()
        conn.close()
        return True

    def has_liked(self, post_id, user_email):
        user_email = self.normalize_email(user_email)
        if not user_email:
            return False

        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1
            FROM post_likes
            WHERE post_id = ? AND user_email = ?
            LIMIT 1
        """, (post_id, user_email))
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def toggle_like(self, post_id, user_email):
        if self.has_liked(post_id, user_email):
            self.unlike_post(post_id, user_email)
            return False
        self.like_post(post_id, user_email)
        return True

    def get_like_count(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM post_likes WHERE post_id = ?", (post_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    # ---------------- FETCH POSTS ----------------

    def get_post_with_tags(self, post_id, viewer_email):
        viewer_email = self.normalize_email(viewer_email)

        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                p.post_id,
                p.post_title,
                p.post_content,
                p.created_at,
                p.email,
                COALESCE(GROUP_CONCAT(t.tag_name, ', '), '') AS tags,
                (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.post_id) AS like_count,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM post_likes pl2
                        WHERE pl2.post_id = p.post_id AND pl2.user_email = ?
                    ) THEN 1
                    ELSE 0
                END AS liked_by_me
            FROM posts p
            LEFT JOIN post_tags pt ON pt.post_id = p.post_id
            LEFT JOIN tags t ON t.tag_id = pt.tag_id
            WHERE p.post_id = ?
            GROUP BY p.post_id
        """, (viewer_email, post_id))

        row = cursor.fetchone()
        conn.close()
        return row

    def get_all_posts_with_tags(self, sort="newest", viewer_email=""):
        viewer_email = self.normalize_email(viewer_email)

        conn = self._connect()
        cursor = conn.cursor()

        if sort == "oldest":
            order_by = "p.created_at ASC"
        elif sort == "title":
            order_by = "p.post_title COLLATE NOCASE ASC"
        else:
            order_by = "p.created_at DESC"

        cursor.execute(f"""
            SELECT
                p.post_id,
                p.post_title,
                p.post_content,
                p.created_at,
                p.email,
                COALESCE(GROUP_CONCAT(t.tag_name, ', '), '') AS tags,
                (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.post_id) AS like_count,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM post_likes pl2
                        WHERE pl2.post_id = p.post_id AND pl2.user_email = ?
                    ) THEN 1
                    ELSE 0
                END AS liked_by_me
            FROM posts p
            LEFT JOIN post_tags pt ON pt.post_id = p.post_id
            LEFT JOIN tags t ON t.tag_id = pt.tag_id
            GROUP BY p.post_id
            ORDER BY {order_by}
        """, (viewer_email,))

        rows = cursor.fetchall()
        conn.close()
        return rows

    def search_posts_with_tags(self, q, sort="newest", viewer_email=""):
        viewer_email = self.normalize_email(viewer_email)
        q = (q or "").strip().lower()

        conn = self._connect()
        cursor = conn.cursor()

        like = f"%{q}%"

        if sort == "oldest":
            order_by = "p.created_at ASC"
        elif sort == "title":
            order_by = "p.post_title COLLATE NOCASE ASC"
        else:
            order_by = "p.created_at DESC"

        cursor.execute(f"""
            SELECT
                p.post_id,
                p.post_title,
                p.post_content,
                p.created_at,
                p.email,
                COALESCE(GROUP_CONCAT(t.tag_name, ', '), '') AS tags,
                (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.post_id) AS like_count,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM post_likes pl2
                        WHERE pl2.post_id = p.post_id AND pl2.user_email = ?
                    ) THEN 1
                    ELSE 0
                END AS liked_by_me
            FROM posts p
            LEFT JOIN post_tags pt ON pt.post_id = p.post_id
            LEFT JOIN tags t ON t.tag_id = pt.tag_id
            WHERE
                LOWER(p.post_title) LIKE ?
                OR LOWER(p.post_content) LIKE ?
                OR LOWER(t.tag_name) LIKE ?
            GROUP BY p.post_id
            ORDER BY {order_by}
        """, (viewer_email, like, like, like))

        rows = cursor.fetchall()
        conn.close()
        return rows

    # ---------------- COMMENTS ----------------

    def add_comment(self, post_id, comment_text):
        comment_text = (comment_text or "").strip()
        if comment_text == "":
            return None

        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO comments (post_id, comment_text, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (post_id, comment_text))
        comment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return comment_id

    def get_comments_for_post(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT comment_id, post_id, comment_text, created_at
            FROM comments
            WHERE post_id = ?
            ORDER BY created_at DESC
        """, (post_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def delete_comment(self, comment_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comments WHERE comment_id = ?", (comment_id,))
        conn.commit()
        conn.close()

    def update_comment(self, comment_id, new_text):
        new_text = (new_text or "").strip()
        if new_text == "":
            return False

        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE comments
            SET comment_text = ?, created_at = created_at
            WHERE comment_id = ?
        """, (new_text, comment_id))
        conn.commit()
        conn.close()
        return True

    def get_comment(self, comment_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT comment_id, post_id, comment_text, created_at
            FROM comments
            WHERE comment_id = ?
        """, (comment_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_latest_comment_preview_for_posts(self, post_ids):
        if not post_ids:
            return {}

        conn = self._connect()
        cursor = conn.cursor()

        placeholders = ",".join(["?"] * len(post_ids))

        cursor.execute(f"""
            SELECT c.post_id, c.comment_text, c.created_at
            FROM comments c
            JOIN (
                SELECT post_id, MAX(created_at) AS max_created_at
                FROM comments
                WHERE post_id IN ({placeholders})
                GROUP BY post_id
            ) latest
            ON latest.post_id = c.post_id AND latest.max_created_at = c.created_at
        """, post_ids)

        rows = cursor.fetchall()
        conn.close()
        return {r[0]: (r[1], r[2]) for r in rows}

    # ---------------- IMAGES ----------------

    def add_post_image(self, post_id, filename):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO post_images (post_id, filename, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (post_id, filename))
        conn.commit()
        conn.close()

    def get_images_for_post(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT image_id, post_id, filename, created_at
            FROM post_images
            WHERE post_id = ?
            ORDER BY created_at ASC
        """, (post_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_first_image_for_posts(self, post_ids):
        if not post_ids:
            return {}

        conn = self._connect()
        cursor = conn.cursor()

        placeholders = ",".join(["?"] * len(post_ids))

        cursor.execute(f"""
            SELECT pi.post_id, pi.filename
            FROM post_images pi
            JOIN (
                SELECT post_id, MIN(created_at) AS min_created_at
                FROM post_images
                WHERE post_id IN ({placeholders})
                GROUP BY post_id
            ) firsts
            ON firsts.post_id = pi.post_id AND firsts.min_created_at = pi.created_at
        """, post_ids)

        rows = cursor.fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}

    def get_post_image(self, image_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT image_id, post_id, filename, created_at
            FROM post_images
            WHERE image_id = ?
        """, (image_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def delete_post_image(self, image_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM post_images WHERE image_id = ?", (image_id,))
        conn.commit()
        conn.close()
