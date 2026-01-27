"""
Main entry point:
- Create Flask app
- Apply config
- Ensure folders exist
- Register route modules
- Run server
"""

from flask import Flask

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

    return app


app = create_app()

# To be integrated with homepage
@app.route("/home")
def home():
    return "<h1>Home page coming soon</h1>"

if __name__ == "__main__":
    app.run(debug=True)
