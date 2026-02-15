"""
Services module for the messaging app
Handles database operations and Socket.IO events
UPDATED: Uses EMAIL instead of user_id for easier searching
"""

import sqlite3
import os
from flask_socketio import join_room, leave_room

try:
    from config import DATA_DIR
except ImportError:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")

# Database file paths
DB_FILE = os.path.join(DATA_DIR, "messaging.db")
MEDIA_DB_FILE = os.path.join(DATA_DIR, "media.db")


def get_db():
    """Get main database connection with row factory"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def get_media_db():
    """Get media database connection with row factory"""
    conn = sqlite3.connect(MEDIA_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# services.py (excerpt)

# services.py (excerpt)

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # Chats table – using email addresses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            nickname TEXT NOT NULL,
            creator_email TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_email, creator_email)
        )
    """)

    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            sender_email TEXT NOT NULL,
            content TEXT,
            media_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE
        )
    """)

    # Indexes (optional but recommended)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chats_participants ON chats(user_email, creator_email)")

    conn.commit()
    conn.close()
    print("✅ Main database initialized (email schema)")

def init_media_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_media_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            sender_email TEXT NOT NULL,
            filename TEXT NOT NULL,
            data TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_chat_id ON media(chat_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_uploaded_at ON media(uploaded_at)")

    conn.commit()
    conn.close()
    print("✅ Media database initialized (email schema)")


def register_socket_events(socketio):
    """Register Socket.IO events for real-time messaging"""
    
    @socketio.on('connect')
    def handle_connect():
        print('✅ Client connected to Socket.IO')

    @socketio.on('disconnect')
    def handle_disconnect():
        print('❌ Client disconnected from Socket.IO')

    @socketio.on('join_chat')
    def handle_join_chat(data):
        """Join a chat room for real-time updates"""
        chat_id = data.get('chat_id')
        if chat_id:
            room = f'chat_{chat_id}'
            join_room(room)
            print(f'👥 User joined chat room: {room}')

    @socketio.on('leave_chat')
    def handle_leave_chat(data):
        """Leave a chat room"""
        chat_id = data.get('chat_id')
        if chat_id:
            room = f'chat_{chat_id}'
            leave_room(room)
            print(f'👋 User left chat room: {room}')

    @socketio.on('typing')
    def handle_typing(data):
        """Handle typing indicators"""
        chat_id = data.get('chat_id')
        user_email = data.get('user_email')
        is_typing = data.get('is_typing', False)
        
        if chat_id:
            socketio.emit('user_typing', {
                'user_email': user_email,
                'is_typing': is_typing
            }, room=f'chat_{chat_id}', include_self=False)

    print("✅ Socket.IO events registered")