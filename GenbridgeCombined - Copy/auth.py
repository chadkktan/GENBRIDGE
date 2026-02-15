"""
Authentication helper for messaging app
Integrates with teammate's user management system
"""

import json
import os
from config import USERS_FILE, PROFILES_FILE


def get_user_by_id(user_id):
    """
    Get user information from users.json (your teammate's system)
    
    Args:
        user_id: The user ID to look up
        
    Returns:
        dict: User info or None if not found
        Example: {
            "user_id": "user_123",
            "name": "John Doe",
            "email": "john@example.com",
            "avatar": "/static/uploads/avatar.jpg"
        }
    """
    if not os.path.exists(USERS_FILE):
        return None
    
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
            
        # Assuming users.json structure (adjust based on your teammate's format)
        # Option 1: List of users
        if isinstance(users, list):
            for user in users:
                if user.get('email', '').lower() == user_id.lower() or user.get('id') == user_id:
                    return user
        
        # Option 2: Dictionary with user_id as keys
        elif isinstance(users, dict):
            return users.get(user_id)
            
    except (json.JSONDecodeError, FileNotFoundError):
        return None
    
    return None


def get_current_user_from_session(session):
    """
    Get current logged-in user from Flask session
    
    Args:
        session: Flask session object
        
    Returns:
        dict: User info including user_id, name, email, etc.
        None: If user not logged in
    """
    email = session.get('user_email')
    if not email:
        return None
    # fetch from your JSON DB or wherever you store user info
    user = get_user_by_email(email)  # returns dict with 'email', 'name', etc.
    return user   # must contain 'email'


def get_user_by_email(email):
    """
    Get user information from users.json by email
    
    Args:
        email: The user's email to look up
        
    Returns:
        dict: User info or None if not found
    """
    if not os.path.exists(USERS_FILE):
        return None
    
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
            
        # Handle list format
        if isinstance(users, list):
            for user in users:
                if user.get('email', '').lower() == email.lower():
                    return {
                        'email': user.get('email'),
                        'name': user.get('name') or user.get('full_name', 'Unknown User'),
                        'avatar': user.get('avatar', '/static/default-avatar.png')
                    }
        
        # Handle dict format (keyed by email)
        elif isinstance(users, dict):
            user = users.get(email)
            if user:
                return {
                    'email': email,
                    'name': user.get('name') or user.get('full_name', 'Unknown User'),
                    'avatar': user.get('avatar', '/static/default-avatar.png')
                }
            
    except (json.JSONDecodeError, FileNotFoundError):
        return None
    
    return None

def require_login(f):
    """
    Decorator to require user to be logged in
    
    Usage:
        @app.route('/messages')
        @require_login
        def messages():
            return render_template('messages.html')
    """
    from functools import wraps
    from flask import session, redirect, url_for, flash
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        email = session.get('auth_email') or session.get('email') or session.get('user_email')
        if not email:
            flash('Please log in to access messages', 'error')
            return redirect(url_for('sign_in'))
        return f(*args, **kwargs)
    return decorated_function


def search_users(query):
    """
    Search for users by name or email (for adding new chats)
    
    Args:
        query: Search string
        
    Returns:
        list: Matching users with email, name, avatar
    """
    if not os.path.exists(USERS_FILE):
        return []
    
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        
        query_lower = query.lower()
        results = []
        
        # Handle list format
        if isinstance(users, list):
            for user in users:
                name = (user.get('name') or user.get('full_name', '')).lower()
                email = user.get('email', '').lower()
                
                if query_lower in name or query_lower in email:
                    results.append({
                        'email': user.get('email'),
                        'name': user.get('name') or user.get('full_name', 'Unknown'),
                        'avatar': user.get('avatar', '/static/default-avatar.png')
                    })
        
        # Handle dict format (keyed by email)
        elif isinstance(users, dict):
            for email, user_data in users.items():
                name = (user_data.get('name') or user_data.get('full_name', '')).lower()
                email_lower = email.lower()
                
                if query_lower in name or query_lower in email_lower:
                    results.append({
                        'email': email,
                        'name': user_data.get('name') or user_data.get('full_name', 'Unknown'),
                        'avatar': user_data.get('avatar', '/static/default-avatar.png')
                    })
        
        return results[:10]  # Limit to 10 results
        
    except (json.JSONDecodeError, FileNotFoundError):
        return []
    
def get_current_user_from_session(session):
    """
    Get current logged-in user from Flask session
    
    Args:
        session: Flask session object
        
    Returns:
        dict: User info including email, name, avatar
        None: If user not logged in
    """
    # Try different session keys
    email = session.get('auth_email') or session.get('email') or session.get('user_email')
    
    if not email:
        return None
    
    # Get full user info
    user = get_user_by_email(email)
    
    if user:
        return user
    
    # Fallback if user not in JSON
    return {
        'email': email,
        'name': email.split('@')[0].title(),
        'avatar': '/static/default-avatar.png'
    }