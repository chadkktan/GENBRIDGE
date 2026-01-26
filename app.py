"""
Main entry point:
- Create Flask app
- Apply config
- Ensure folders exist
- Register route modules
- Run server
"""

from flask import Flask, json, render_template, request, jsonify
from flask_socketio import SocketIO, send, emit
from config import SECRET_KEY, ensure_dirs
from database import db
from routes_auth import register_auth_routes
from routes_profile import register_profile_routes


def create_app() -> Flask:
    ensure_dirs()

    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    # Attach routes from separate route files
    register_auth_routes(app, db)
    register_profile_routes(app, db)
    @app.route('/')
    def home():
        return render_template('home.html')

    @app.route('/messages')
    def messages():
        return render_template('messages.html')

    @app.route('/settings')
    def settings():
        return render_template('settings.html')

    @app.route('/api/send', methods=['POST'])
    def send_message():
        data = request.get_json()
        message = data.get('text')
        print("Message received:", message)
        return jsonify({"status": "success"})
    @socketio.on('my event')
    def handle_my_custom_event(json):
        print('received json: ' + str(json))
    @socketio.on('message')
    def handle_message(message):
        send(message)

    @socketio.on('json')
    def handle_json(json):
        send(json, json=True)

    @socketio.on('my event')
    def handle_my_custom_event(json):
        emit('my response', json)
    return app

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

