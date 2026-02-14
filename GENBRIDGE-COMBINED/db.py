"""
Database initialization script
Creates messaging.db and media.db with correct schema
"""

import sqlite3
import os

# Create data directory
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

print("🔧 Creating databases...")

# ==========================================
# MAIN DATABASE (messaging.db)
# ==========================================
conn = sqlite3.connect(os.path.join(DATA_DIR, "messaging.db"))
cursor = conn.cursor()

print("📋 Creating main database tables...")

# CHATS TABLE
# Note: Uses TEXT for user_id and creator_id (NOT INTEGER)
# This matches what __init__.py expects ("current_user", "user_001", etc.)
cursor.execute("""
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    nickname TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, creator_id)
)
""")
print("  ✅ chats table created")

# MESSAGES TABLE
cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    sender_id TEXT NOT NULL,
    content TEXT,
    media_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
)
""")
print("  ✅ messages table created")

# CREATE INDEXES
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_chat_id 
    ON messages(chat_id)
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
    ON messages(timestamp)
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_chats_participants
    ON chats(user_id, creator_id)
""")
print("  ✅ indexes created")

conn.commit()
conn.close()

# ==========================================
# MEDIA DATABASE (media.db)
# ==========================================
media_conn = sqlite3.connect(os.path.join(DATA_DIR, "media.db"))
media_cursor = media_conn.cursor()

print("📁 Creating media database tables...")

# MEDIA TABLE
media_cursor.execute("""
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    sender_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    data TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
print("  ✅ media table created")

# CREATE INDEXES
media_cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_media_chat_id 
    ON media(chat_id)
""")

media_cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_media_uploaded_at 
    ON media(uploaded_at)
""")
print("  ✅ indexes created")

media_conn.commit()
media_conn.close()

print("\n✅ Databases created successfully!")
print(f"   📁 {os.path.join(DATA_DIR, 'messaging.db')}")
print(f"   📁 {os.path.join(DATA_DIR, 'media.db')}")
print("\n💡 Schema matches what __init__.py expects:")
print("   - user_id: TEXT (not INTEGER)")
print("   - creator_id: TEXT (not INTEGER)")
print("   - Column names: id (not chat_id/message_id)")