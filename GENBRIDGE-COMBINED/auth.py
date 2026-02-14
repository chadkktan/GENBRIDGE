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
                if user.get('user_id') == user_id or user.get('id') == user_id:
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
    user_id = session.get('user_id')
    
    if not user_id:
        return None
    
    # Get full user info from your teammate's system
    user = get_user_by_id(user_id)
    
    if user:
        return {
            'user_id': user.get('user_id') or user.get('id'),
            'name': user.get('name', 'Unknown User'),
            'email': user.get('email', ''),
            'avatar': user.get('avatar', '/static/default-avatar.png')
        }
    
    return None


def get_profile_by_user_id(user_id):
    """
    Get user profile from profiles.json (your teammate's system)
    
    Args:
        user_id: The user ID to look up
        
    Returns:
        dict: Profile info or None if not found
    """
    if not os.path.exists(PROFILES_FILE):
        return None
    
    try:
        with open(PROFILES_FILE, 'r') as f:
            profiles = json.load(f)
            
        # Adjust based on your teammate's structure
        if isinstance(profiles, list):
            for profile in profiles:
                if profile.get('user_id') == user_id or profile.get('id') == user_id:
                    return profile
        elif isinstance(profiles, dict):
            return profiles.get(user_id)
            
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
        if 'user_id' not in session:
            flash('Please log in to access messages', 'error')
            return redirect(url_for('login'))  # Adjust to your login route
        return f(*args, **kwargs)
    return decorated_function


def search_users(query):
    """
    Search for users by name or email (for adding new chats)
    
    Args:
        query: Search string
        
    Returns:
        list: Matching users
    """
    if not os.path.exists(USERS_FILE):
        return []
    
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        
        query_lower = query.lower()
        results = []
        
        users_list = users if isinstance(users, list) else users.values()
        
        for user in users_list:
            name = user.get('name', '').lower()
            email = user.get('email', '').lower()
            user_id = str(user.get('user_id', user.get('id', ''))).lower()
            
            if query_lower in name or query_lower in email or query_lower in user_id:
                results.append({
                    'user_id': user.get('user_id') or user.get('id'),
                    'name': user.get('name', 'Unknown'),
                    'email': user.get('email', ''),
                    'avatar': user.get('avatar', '/static/default-avatar.png')
                })
        
        return results[:10]  # Limit to 10 results
        
    except (json.JSONDecodeError, FileNotFoundError):
        return []


# Example users.json structure (for reference):
"""
Option 1 - List format:
[
    {
        "user_id": "user_001",
        "name": "John Doe",
        "email": "john@example.com",
        "avatar": "/static/uploads/john.jpg"
    },
    {
        "user_id": "user_002",
        "name": "Jane Smith",
        "email": "jane@example.com",
        "avatar": "/static/uploads/jane.jpg"
    }
]

Option 2 - Dictionary format:
{
    "user_001": {
        "name": "John Doe",
        "email": "john@example.com",
        "avatar": "/static/uploads/john.jpg"
    },
    "user_002": {
        "name": "Jane Smith",
        "email": "jane@example.com",
        "avatar": "/static/uploads/jane.jpg"
    }
}
"""