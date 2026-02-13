import sqlite3

DATABASE = "communities.db"

def connect_db():
   
    conn = sqlite3.connect(DATABASE, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=10000;")  
    return conn

# community_db.py
def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS communities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                members INTEGER DEFAULT 0,
                created_by_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()



def increment_members(community_id):
    with connect_db() as conn:
        conn.execute(
            "UPDATE communities SET members = members + 1 WHERE id = ?",
            (community_id,)
        )
        conn.commit()

# community_db.py (add this helper)
def add_created_by_column_if_missing():
    with connect_db() as conn:
        try:
            conn.execute("ALTER TABLE communities ADD COLUMN created_by_email TEXT")
            conn.commit()
        except Exception:
            # column already exists
            pass

def ensure_created_by_column():
    with connect_db() as conn:
        # Check if column already exists
        cols = conn.execute("PRAGMA table_info(communities)").fetchall()
        col_names = [c["name"] for c in cols]
        if "created_by_email" not in col_names:
            conn.execute("ALTER TABLE communities ADD COLUMN created_by_email TEXT")
            conn.commit()

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

def create_community(name, category, description, created_by_email):
    with connect_db() as conn:
        conn.execute(
            """INSERT INTO communities 
               (name, category, description, members, created_by_email)
               VALUES (?, ?, ?, ?, ?)""",

            (name, category, description, 1, created_by_email)  # ✅ START AT 1
        )
        conn.commit()

def update_community(community_id, name, category, description):
    with connect_db() as conn:
        conn.execute(
            """UPDATE communities
               SET name = ?, category = ?, description = ?
               WHERE id = ?""",
            (name, category, description, community_id)
        )
        conn.commit()

def delete_community(community_id):
    with connect_db() as conn:
        conn.execute(
            "DELETE FROM communities WHERE id = ?",
            (community_id,)
        )
        conn.commit()

def ensure_members_table():
    """Create a membership table to prevent duplicate joins."""
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS community_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                community_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(community_id, email)
            )
        """)
        conn.commit()


def has_joined(community_id, email) -> bool:
    with connect_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM community_members WHERE community_id = ? AND email = ? LIMIT 1",
            (community_id, email)
        ).fetchone()
        return row is not None


def join_community_once(community_id, email) -> bool:
    """
    Try to join community.
    Returns True if joined successfully (first time),
    False if user already joined.
    """
    with connect_db() as conn:
        # Insert membership only if not exists (thanks to UNIQUE constraint)
        cur = conn.execute(
            "INSERT OR IGNORE INTO community_members (community_id, email) VALUES (?, ?)",
            (community_id, email)
        )

        # If row was inserted, rowcount will be 1; if ignored, rowcount will be 0
        if cur.rowcount == 1:
            conn.execute(
                "UPDATE communities SET members = members + 1 WHERE id = ?",
                (community_id,)
            )
            conn.commit()
            return True

        conn.commit()
        return False

def leave_community_once(community_id, email) -> bool:
    """
    Leave community.
    Returns True if user was a member,
    False if user was not a member.
    """
    with connect_db() as conn:
        cur = conn.execute(
            "DELETE FROM community_members WHERE community_id = ? AND email = ?",
            (community_id, email)
        )

        if cur.rowcount == 1:
            conn.execute(
                "UPDATE communities SET members = members - 1 WHERE id = ? AND members > 0",
                (community_id,)
            )
            conn.commit()
            return True

        conn.commit()
        return False