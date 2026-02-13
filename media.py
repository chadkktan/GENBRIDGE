import sqlite3
import os

os.makedirs("data", exist_ok=True)

conn = sqlite3.connect("data/media.db")
cursor = conn.cursor()

cursor.execute("""
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

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_media_chat_id 
    ON media(chat_id)
""")

conn.commit()
conn.close()

print("✅ Media database created successfully!")