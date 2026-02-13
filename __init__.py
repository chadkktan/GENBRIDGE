from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime
import traceback

from services import (
    get_db,
    get_media_db,
    init_db,
    init_media_db,
    register_socket_events
)

socketio = SocketIO(cors_allowed_origins="*")


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "secret!"
    socketio.init_app(app)

    init_db()
    init_media_db()
    register_socket_events(socketio)

    # -------------------------
    # Pages
    # -------------------------
    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/messages")
    def messages():
        return render_template("messages.html")

    @app.route("/community")
    def community():
        return render_template("community.html")
    # -------------------------
    # API: Chats (Private)
    # -------------------------
    @app.route("/api/chats", methods=["POST"])
    def create_chat():
        """Create a new PRIVATE chat between two users"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "Invalid JSON"}), 400

            profileid = data.get("profileid") or data.get("user_id")
            nickname = data.get("nickname", "")
            creator_id = data.get("creator_id", "current_user")

            if not profileid:
                return jsonify({
                    "status": "error", 
                    "message": "Profile ID is required"
                }), 400

            if not nickname:
                return jsonify({
                    "status": "error", 
                    "message": "Nickname is required"
                }), 400

            conn = get_db()
            cursor = conn.cursor()

            # Check if private chat already exists between these two users
            cursor.execute("""
                SELECT id FROM chats 
                WHERE (user_id = ? AND creator_id = ?) 
                   OR (user_id = ? AND creator_id = ?)
            """, (profileid, creator_id, creator_id, profileid))
            existing = cursor.fetchone()
            
            if existing:
                conn.close()
                print(f"⚠️  Private chat already exists between {creator_id} and {profileid}")
                return jsonify({
                    "status": "error", 
                    "message": "Chat already exists",
                    "chat_id": existing["id"]
                }), 409

            # Insert new PRIVATE chat
            cursor.execute("""
                INSERT INTO chats (user_id, nickname, creator_id, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (profileid, nickname, creator_id))

            conn.commit()
            chat_id = cursor.lastrowid
            conn.close()

            print(f"✅ Private chat created: {nickname} (Chat ID: {chat_id})")
            print(f"   Participants: {creator_id} ↔️ {profileid}")

            chat_data = {
                "chat_id": chat_id,
                "user_id": profileid,
                "nickname": nickname,
                "creator_id": creator_id,
                "last_message": "",
                "last_message_time": None,
                "created_at": datetime.now().isoformat()
            }
            socketio.emit('chat_created', chat_data, namespace='/')

            return jsonify({
                "status": "success", 
                "chat_id": chat_id, 
                "user_id": profileid,
                "nickname": nickname,
                "creator_id": creator_id
            }), 201

        except Exception as e:
            print(f"❌ Error creating chat: {str(e)}")
            traceback.print_exc()
            return jsonify({
                "status": "error", 
                "message": f"Server error: {str(e)}"
            }), 500

    @app.route("/api/chats", methods=["GET"])
    def get_chats():
        """Get all PRIVATE chats for current user (passed as query param)"""
        try:
            # In production, get this from session/auth
            user_id = request.args.get('user_id', 'current_user')
            
            print(f"📋 GET /api/chats called for user: {user_id}")
            conn = get_db()
            cursor = conn.cursor()

            # Get chats where user is EITHER creator OR recipient
            cursor.execute("""
                SELECT 
                    c.id AS chat_id, 
                    c.user_id, 
                    c.nickname,
                    c.creator_id,
                    c.created_at,
                    (
                        SELECT m.content 
                        FROM messages m 
                        WHERE m.chat_id = c.id 
                        ORDER BY m.timestamp DESC 
                        LIMIT 1
                    ) AS last_message,
                    (
                        SELECT m.timestamp 
                        FROM messages m 
                        WHERE m.chat_id = c.id 
                        ORDER BY m.timestamp DESC 
                        LIMIT 1
                    ) AS last_message_time
                FROM chats c
                WHERE c.user_id = ? OR c.creator_id = ?
                ORDER BY 
                    CASE 
                        WHEN last_message_time IS NULL THEN c.created_at 
                        ELSE last_message_time 
                    END DESC
            """, (user_id, user_id))
            
            rows = cursor.fetchall()
            conn.close()

            chats = []
            for row in rows:
                chats.append({
                    "chat_id": row["chat_id"],
                    "user_id": row["user_id"],
                    "nickname": row["nickname"],
                    "creator_id": row["creator_id"],
                    "last_message": row["last_message"] or "",
                    "last_message_time": row["last_message_time"],
                    "created_at": row["created_at"]
                })

            print(f"📋 Returned {len(chats)} private chats for {user_id}")
            return jsonify({"status": "success", "chats": chats}), 200

        except Exception as e:
            print(f"❌ Error getting chats: {str(e)}")
            traceback.print_exc()
            return jsonify({
                "status": "error", 
                "message": f"Server error: {str(e)}"
            }), 500

    @app.route("/api/chats/<int:chat_id>", methods=["DELETE"])
    def delete_chat(chat_id):
        """Delete a chat and all its messages"""
        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("SELECT id, nickname FROM chats WHERE id = ?", (chat_id,))
            chat = cursor.fetchone()
            if not chat:
                conn.close()
                return jsonify({
                    "status": "error", 
                    "message": "Chat not found"
                }), 404

            # Delete all messages
            cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            
            # Delete media files associated with this chat
            media_conn = get_media_db()
            media_cursor = media_conn.cursor()
            media_cursor.execute("DELETE FROM media WHERE chat_id = ?", (chat_id,))
            media_conn.commit()
            media_conn.close()
            
            # Delete chat
            cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            
            conn.commit()
            conn.close()

            print(f"🗑️  Chat deleted: {chat['nickname']} (Chat ID: {chat_id})")

            socketio.emit('chat_deleted', {"chat_id": chat_id}, namespace='/')

            return jsonify({"status": "success", "message": "Chat deleted"}), 200

        except Exception as e:
            print(f"❌ Error deleting chat: {str(e)}")
            traceback.print_exc()
            return jsonify({
                "status": "error", 
                "message": f"Server error: {str(e)}"
            }), 500

    # -------------------------
    # API: Messages
    # -------------------------
    @app.route("/api/messages/send", methods=["POST"])
    def send_message():
        """Send a text message"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"status": "error", "message": "Invalid JSON"}), 400

            chat_id = data.get("chat_id")
            sender_id = data.get("sender_id")
            content = data.get("content", "").strip()

            if not chat_id or not sender_id:
                return jsonify({
                    "status": "error", 
                    "message": "Chat ID and Sender ID are required"
                }), 400

            if not content:
                return jsonify({
                    "status": "error", 
                    "message": "Message content is required"
                }), 400

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("SELECT nickname, user_id, creator_id FROM chats WHERE id = ?", (chat_id,))
            chat = cursor.fetchone()
            if not chat:
                conn.close()
                return jsonify({
                    "status": "error", 
                    "message": "Chat not found"
                }), 404

            # Insert message (without media)
            cursor.execute("""
                INSERT INTO messages (chat_id, sender_id, content, timestamp)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (chat_id, sender_id, content))

            conn.commit()
            message_id = cursor.lastrowid
            
            cursor.execute("SELECT timestamp FROM messages WHERE id = ?", (message_id,))
            timestamp = cursor.fetchone()['timestamp']
            conn.close()

            # Determine recipient
            recipient_id = chat['user_id'] if sender_id == chat['creator_id'] else chat['creator_id']
            recipient_name = chat['nickname']
            
            print(f"💬 Message sent in Chat {chat_id}:")
            print(f"   From: {sender_id} → To: {recipient_name} ({recipient_id})")
            print(f"   Message ID: {message_id}")
            print(f"   Content: \"{content}\"")

            message_data = {
                "message_id": message_id,
                "chat_id": chat_id,
                "sender_id": sender_id,
                "content": content,
                "media_url": None,
                "media_type": None,
                "timestamp": timestamp
            }
            socketio.emit('new_message', message_data, namespace='/')

            return jsonify({
                "status": "success", 
                "message_id": message_id
            }), 201

        except Exception as e:
            print(f"❌ Error sending message: {str(e)}")
            traceback.print_exc()
            return jsonify({
                "status": "error", 
                "message": f"Server error: {str(e)}"
            }), 500

    @app.route("/api/media/upload", methods=["POST"])
    def upload_media():
        """Upload media file to separate database"""
        try:
            data = request.get_json()
            
            chat_id = data.get("chat_id")
            sender_id = data.get("sender_id")
            filename = data.get("filename")
            file_data = data.get("data")  # Base64
            mime_type = data.get("mime_type")

            if not all([chat_id, sender_id, filename, file_data, mime_type]):
                return jsonify({
                    "status": "error", 
                    "message": "Missing required fields"
                }), 400

            # Save to media database
            media_conn = get_media_db()
            media_cursor = media_conn.cursor()

            media_cursor.execute("""
                INSERT INTO media (chat_id, sender_id, filename, data, mime_type, uploaded_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (chat_id, sender_id, filename, file_data, mime_type))

            media_conn.commit()
            media_id = media_cursor.lastrowid
            
            media_cursor.execute("SELECT uploaded_at FROM media WHERE id = ?", (media_id,))
            uploaded_at = media_cursor.fetchone()['uploaded_at']
            media_conn.close()

            # Create message reference in main database
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("SELECT nickname, user_id, creator_id FROM chats WHERE id = ?", (chat_id,))
            chat = cursor.fetchone()
            
            content = f"Shared {mime_type.split('/')[0]}: {filename}"
            
            cursor.execute("""
                INSERT INTO messages (chat_id, sender_id, content, media_id, timestamp)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (chat_id, sender_id, content, media_id))

            conn.commit()
            message_id = cursor.lastrowid
            
            cursor.execute("SELECT timestamp FROM messages WHERE id = ?", (message_id,))
            timestamp = cursor.fetchone()['timestamp']
            conn.close()

            # Determine recipient
            recipient_id = chat['user_id'] if sender_id == chat['creator_id'] else chat['creator_id']
            recipient_name = chat['nickname']
            
            print(f"💬 Media message sent in Chat {chat_id}:")
            print(f"   From: {sender_id} → To: {recipient_name} ({recipient_id})")
            print(f"   Message ID: {message_id}, Media ID: {media_id}")
            print(f"   File: {filename} ({mime_type})")

            message_data = {
                "message_id": message_id,
                "chat_id": chat_id,
                "sender_id": sender_id,
                "content": content,
                "media_url": file_data,  # Send base64 for display
                "media_type": mime_type,
                "timestamp": timestamp
            }
            socketio.emit('new_message', message_data, namespace='/')

            return jsonify({
                "status": "success", 
                "message_id": message_id,
                "media_id": media_id
            }), 201

        except Exception as e:
            print(f"❌ Error uploading media: {str(e)}")
            traceback.print_exc()
            return jsonify({
                "status": "error", 
                "message": f"Server error: {str(e)}"
            }), 500

    @app.route("/api/messages/<int:message_id>", methods=["PUT"])
    def edit_message(message_id):
        """Edit a message"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"status": "error", "message": "Invalid JSON"}), 400

            content = data.get("content", "").strip()

            if not content:
                return jsonify({
                    "status": "error", 
                    "message": "Message content is required"
                }), 400

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("SELECT chat_id, sender_id FROM messages WHERE id = ?", (message_id,))
            
            result = cursor.fetchone()
            if not result:
                conn.close()
                return jsonify({
                    "status": "error", 
                    "message": "Message not found"
                }), 404

            chat_id = result['chat_id']
            sender_id = result['sender_id']

            cursor.execute("UPDATE messages SET content = ? WHERE id = ?", (content, message_id))

            conn.commit()
            conn.close()

            print(f"✏️  Message edited:")
            print(f"   Message ID: {message_id} in Chat {chat_id}")
            print(f"   Sender: {sender_id}")
            print(f"   New content: \"{content}\"")

            socketio.emit('message_edited', {
                "message_id": message_id,
                "chat_id": chat_id,
                "content": content
            }, namespace='/')

            return jsonify({
                "status": "success", 
                "message_id": message_id
            }), 200

        except Exception as e:
            print(f"❌ Error editing message: {str(e)}")
            traceback.print_exc()
            return jsonify({
                "status": "error", 
                "message": f"Server error: {str(e)}"
            }), 500

    @app.route("/api/messages/<int:message_id>", methods=["DELETE"])
    def delete_message(message_id):
        """Delete a message"""
        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("SELECT chat_id, sender_id, content, media_id FROM messages WHERE id = ?", (message_id,))
            
            result = cursor.fetchone()
            if not result:
                conn.close()
                return jsonify({
                    "status": "error", 
                    "message": "Message not found"
                }), 404

            chat_id = result['chat_id']
            sender_id = result['sender_id']
            content = result['content']
            media_id = result['media_id']

            # Delete associated media if exists
            if media_id:
                media_conn = get_media_db()
                media_cursor = media_conn.cursor()
                media_cursor.execute("DELETE FROM media WHERE id = ?", (media_id,))
                media_conn.commit()
                media_conn.close()

            cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            
            conn.commit()
            conn.close()

            print(f"🗑️  Message deleted:")
            print(f"   Message ID: {message_id} from Chat {chat_id}")
            print(f"   Sender: {sender_id}")
            print(f"   Content: \"{content}\"")

            socketio.emit('message_deleted', {
                "message_id": message_id,
                "chat_id": chat_id
            }, namespace='/')

            return jsonify({
                "status": "success", 
                "message": "Message deleted"
            }), 200

        except Exception as e:
            print(f"❌ Error deleting message: {str(e)}")
            traceback.print_exc()
            return jsonify({
                "status": "error", 
                "message": f"Server error: {str(e)}"
            }), 500

    @app.route("/api/messages/<int:chat_id>", methods=["GET"])
    def get_messages(chat_id):
        """Get all messages for a specific chat (with media)"""
        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("SELECT id, nickname FROM chats WHERE id = ?", (chat_id,))
            chat = cursor.fetchone()
            if not chat:
                conn.close()
                return jsonify({
                    "status": "error", 
                    "message": "Chat not found"
                }), 404

            # Get messages
            cursor.execute("""
                SELECT id as message_id, sender_id, content, media_id, timestamp
                FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp ASC
            """, (chat_id,))

            messages = cursor.fetchall()
            conn.close()

            # Get media data for messages with media
            media_conn = get_media_db()
            media_cursor = media_conn.cursor()

            result_messages = []
            for msg in messages:
                msg_dict = dict(msg)
                
                if msg['media_id']:
                    media_cursor.execute("""
                        SELECT data, mime_type FROM media WHERE id = ?
                    """, (msg['media_id'],))
                    media = media_cursor.fetchone()
                    
                    if media:
                        msg_dict['media_url'] = media['data']
                        msg_dict['media_type'] = media['mime_type']
                    else:
                        msg_dict['media_url'] = None
                        msg_dict['media_type'] = None
                else:
                    msg_dict['media_url'] = None
                    msg_dict['media_type'] = None
                
                result_messages.append(msg_dict)

            media_conn.close()

            print(f"📨 Retrieved {len(result_messages)} messages from Chat {chat_id} ({chat['nickname']})")

            return jsonify({
                "status": "success",
                "messages": result_messages
            }), 200

        except Exception as e:
            print(f"❌ Error getting messages: {str(e)}")
            traceback.print_exc()
            return jsonify({
                "status": "error", 
                "message": f"Server error: {str(e)}"
            }), 500

    return app


if __name__ == "__main__":
    app = create_app()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)