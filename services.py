"""
Services module for the messaging app
Handles database operations and Socket.IO events
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


def init_db():
    """Initialize the main database with required tables"""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = get_db()
    cursor = conn.cursor()

    # Create chats table with creator_id for PRIVATE chats
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

    # Create messages table (media stored separately)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            sender_id TEXT NOT NULL,
            content TEXT,
            media_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE
        )
    """)

    # Create indexes
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

    # Check if we need to add creator_id column to existing table
    cursor.execute("PRAGMA table_info(chats)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'creator_id' not in columns:
        print("🔧 Adding creator_id column to chats table for private chats")
        cursor.execute("ALTER TABLE chats ADD COLUMN creator_id TEXT DEFAULT 'current_user'")
        # Remove old unique constraint and add new one
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_participants ON chats(user_id, creator_id)")

    # Check if we need to add media_id column
    cursor.execute("PRAGMA table_info(messages)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'media_id' not in columns:
        print("🔧 Adding media_id column to messages table")
        cursor.execute("ALTER TABLE messages ADD COLUMN media_id INTEGER")

    # Remove old media columns if they exist
    if 'media_url' in columns:
        print("🔧 Removing old media_url column (media now in separate DB)")
        # SQLite doesn't support DROP COLUMN, so we'd need to recreate table
        # For now, just leave it and use media_id instead
    
    if 'media_type' in columns:
        print("🔧 Removing old media_type column (media now in separate DB)")

    conn.commit()
    conn.close()
    print("✅ Main database initialized successfully")


def init_media_db():
    """Initialize the separate media database"""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = get_media_db()
    cursor = conn.cursor()

    # Create media table in separate database
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

    # Create index for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_media_chat_id 
        ON media(chat_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_media_uploaded_at 
        ON media(uploaded_at)
    """)

    conn.commit()
    conn.close()
    print("✅ Media database initialized successfully")


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
        user_id = data.get('user_id')
        is_typing = data.get('is_typing', False)
        
        if chat_id:
            socketio.emit('user_typing', {
                'user_id': user_id,
                'is_typing': is_typing
            }, room=f'chat_{chat_id}', include_self=False)

    print("✅ Socket.IO events registered")