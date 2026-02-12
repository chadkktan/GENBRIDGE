import sqlite3
import os

CURRENT_USER_ID = 1  # PLACEHOLDER USER_ID


class DatabaseHelper:
    def __init__(self, db_name='post_info'):
        self.db_name = db_name
        self.init_database()

    def _connect(self):
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_database(self):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_title TEXT NOT NULL,
                post_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT NOT NULL UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS post_tags (
                post_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (post_id, tag_id),
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                comment_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS post_images (
                image_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS post_likes (
                like_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, user_id),
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        conn.close()

    # ---------------- TAGS ----------------

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

    # ---------------- POSTS ----------------

    def insert_post(self, post_title, post_content, post_tags):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO posts (post_title, post_content, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (post_title, post_content))

        post_id = cursor.lastrowid

        tags = self.normalize_tags(post_tags)
        for tag in tags:
            cursor.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES (?)", (tag,))
            cursor.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (tag,))
            tag_id = cursor.fetchone()[0]
            cursor.execute("INSERT OR IGNORE INTO post_tags (post_id, tag_id) VALUES (?, ?)", (post_id, tag_id))

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
                INSERT INTO post_tags (post_id, tag_id)
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

    # ---------------- LIKES ----------------

    def like_post(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO post_likes (post_id, user_id, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (post_id, CURRENT_USER_ID))  # PLACEHOLDER USER_ID
        conn.commit()
        conn.close()

    def unlike_post(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM post_likes
            WHERE post_id = ? AND user_id = ?
        """, (post_id, CURRENT_USER_ID))  # PLACEHOLDER USER_ID
        conn.commit()
        conn.close()

    def has_liked(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1
            FROM post_likes
            WHERE post_id = ? AND user_id = ?
            LIMIT 1
        """, (post_id, CURRENT_USER_ID))  # PLACEHOLDER USER_ID
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def toggle_like(self, post_id):
        if self.has_liked(post_id):
            self.unlike_post(post_id)
            return False
        self.like_post(post_id)
        return True

    def get_like_count(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM post_likes WHERE post_id = ?", (post_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    # ---------------- FETCH POSTS ----------------

    def get_post_with_tags(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                p.post_id,
                p.post_title,
                p.post_content,
                p.created_at,
                COALESCE(GROUP_CONCAT(t.tag_name, ', '), '') AS tags,
                (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.post_id) AS like_count,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM post_likes pl2
                        WHERE pl2.post_id = p.post_id AND pl2.user_id = ?
                    ) THEN 1
                    ELSE 0
                END AS liked_by_me
            FROM posts p
            LEFT JOIN post_tags pt ON pt.post_id = p.post_id
            LEFT JOIN tags t ON t.tag_id = pt.tag_id
            WHERE p.post_id = ?
            GROUP BY p.post_id
        ''', (CURRENT_USER_ID, post_id))  # PLACEHOLDER USER_ID

        row = cursor.fetchone()
        conn.close()
        return row

    def get_all_posts_with_tags(self, sort="newest"):
        conn = self._connect()
        cursor = conn.cursor()

        if sort == "oldest":
            order_by = "p.created_at ASC"
        elif sort == "title":
            order_by = "p.post_title COLLATE NOCASE ASC"
        else:
            order_by = "p.created_at DESC"

        cursor.execute(f'''
            SELECT
                p.post_id,
                p.post_title,
                p.post_content,
                p.created_at,
                COALESCE(GROUP_CONCAT(t.tag_name, ', '), '') AS tags,
                (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.post_id) AS like_count
            FROM posts p
            LEFT JOIN post_tags pt ON pt.post_id = p.post_id
            LEFT JOIN tags t ON t.tag_id = pt.tag_id
            GROUP BY p.post_id
            ORDER BY {order_by}
        ''')

        rows = cursor.fetchall()
        conn.close()
        return rows

    def search_posts_with_tags(self, q, sort="newest"):
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

        cursor.execute(f'''
            SELECT
                p.post_id,
                p.post_title,
                p.post_content,
                p.created_at,
                COALESCE(GROUP_CONCAT(t.tag_name, ', '), '') AS tags,
                (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.post_id) AS like_count
            FROM posts p
            LEFT JOIN post_tags pt ON pt.post_id = p.post_id
            LEFT JOIN tags t ON t.tag_id = pt.tag_id
            WHERE 
                LOWER(p.post_title) LIKE ?
                OR LOWER(p.post_content) LIKE ?
                OR LOWER(t.tag_name) LIKE ?
            GROUP BY p.post_id
            ORDER BY {order_by}
        ''', (like, like, like))

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
        cursor.execute('''
            INSERT INTO comments (post_id, comment_text, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (post_id, comment_text))
        comment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return comment_id

    def get_comments_for_post(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT comment_id, post_id, comment_text, created_at
            FROM comments
            WHERE post_id = ?
            ORDER BY created_at DESC
        ''', (post_id,))
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
