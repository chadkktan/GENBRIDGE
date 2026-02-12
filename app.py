from flask import Flask, render_template, request, redirect, url_for, flash
from database import (
    init_db, get_all_communities, get_community_by_id,
    create_community, update_community, delete_community
)
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'GenBridge'



# ✅ Single source of truth for categories
CATEGORIES = {
    "exercise": "🚴 Exercise",
    "cooking": "🍳 Cooking",
    "arts_crafts": "🎨 Arts & Crafts",
    "music": "🎶 Music",
    "reading": "📖 Reading",
    "technology": "📱 Technology",
    "wellness": "🏡 Wellness",
}

# Initialize database
init_db()

@app.route('/')
def home():
    communities = get_all_communities()
   
    return render_template('landing.html', communities=communities, categories=CATEGORIES)

@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()   # stores emoji label
        description = request.form.get('description', '').strip()

        create_community(name, category, description)
        flash('Community created successfully!', 'success')
        return redirect(url_for('home'))

    return render_template('create.html', categories=CATEGORIES)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    community = get_community_by_id(id)
    if not community:
        flash('Community not found!', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()   # stores emoji label
        description = request.form.get('description', '').strip()

        update_community(id, name, category, description)
        flash('Community updated successfully!', 'success')
        return redirect(url_for('home'))

    return render_template('edit.html', community=community, categories=CATEGORIES)

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    delete_community(id)
    flash('Community deleted successfully!', 'info')
    return redirect(url_for('home'))

@app.context_processor
def inject_datetime():
    return dict(datetime=datetime)

if __name__ == '__main__':
    app.run(debug=True)