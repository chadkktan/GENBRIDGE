import sqlite3

DATABASE = "community_chats.db"


class CommunityChatsDB:
    def __init__(self, database: str = DATABASE):
        self.database = database

    def connect_db(self):
        conn = sqlite3.connect(self.database, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        return conn

    # -----------------------------
    # TABLE CREATION
    # -----------------------------
    def init_chats_db(self):
        """
        Creates the community_chats table.
        Stored in community_chats.db (separate from communities.db).
        """
        with self.connect_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS community_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    community_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Helpful index for fast "get messages by community"
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_community_chats_community_id_created_at
                ON community_chats (community_id, created_at)
            """)

            conn.commit()

    # -----------------------------
    # SEND MESSAGE
    # -----------------------------
    def add_message(self, community_id: int, email: str, message: str):
        message = (message or "").strip()
        email = (email or "").strip()

        if not message or not email:
            return

        with self.connect_db() as conn:
            conn.execute("""
                INSERT INTO community_chats (community_id, email, message)
                VALUES (?, ?, ?)
            """, (community_id, email, message))
            conn.commit()

    # -----------------------------
    # GET MESSAGES
    # -----------------------------
    def get_messages_for_community(self, community_id: int, limit: int = 200):
        """
        Returns messages in chronological order (oldest → newest).
        """
        # Safety clamp
        limit = max(1, min(int(limit), 1000))

        with self.connect_db() as conn:
            return conn.execute("""
                SELECT id, community_id, email, message, created_at
                FROM community_chats
                WHERE community_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (community_id, limit)).fetchall()

    # -----------------------------
    # DELETE ONE MESSAGE
    # -----------------------------
    def delete_message(self, chat_id: int):
        with self.connect_db() as conn:
            conn.execute("DELETE FROM community_chats WHERE id = ?", (chat_id,))
            conn.commit()

    # -----------------------------
    # DELETE ALL MESSAGES IN A COMMUNITY
    # -----------------------------
    def delete_messages_for_community(self, community_id: int):
        with self.connect_db() as conn:
            conn.execute("DELETE FROM community_chats WHERE community_id = ?", (community_id,))
            conn.commit()
