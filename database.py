import sqlite3

DATABASE = "communities.db"

def connect_db():
   
    conn = sqlite3.connect(DATABASE, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=10000;")  
    return conn

def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS communities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                members INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def get_all_communities():
    with connect_db() as conn:
        return conn.execute(
            "SELECT * FROM communities ORDER BY created_at DESC"
        ).fetchall()

def get_community_by_id(community_id):
    with connect_db() as conn:
        return conn.execute(
            "SELECT * FROM communities WHERE id = ?",
            (community_id,)
        ).fetchone()

def create_community(name, category, description):
    with connect_db() as conn:
        conn.execute(
            """INSERT INTO communities (name, category, description)
               VALUES (?, ?, ?)""",
            (name, category, description)
        )

def update_community(community_id, name, category, description):
    with connect_db() as conn:
        conn.execute(
            """UPDATE communities
               SET name = ?, category = ?, description = ?
               WHERE id = ?""",
            (name, category, description, community_id)
        )

def delete_community(community_id):
    with connect_db() as conn:
        conn.execute(
            "DELETE FROM communities WHERE id = ?",
            (community_id,)
        )
