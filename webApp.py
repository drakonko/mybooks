import os
import math
import database
from flask import Flask, render_template, request, url_for
from urllib.parse import quote

app = Flask(__name__)
app.secret_key = "secret_reading_key_2026"

# Твоят нов публичен адрес за кориците в Supabase
SUPABASE_COVERS_URL = "https://pvajcaorfmgmdptrtdxh.supabase.co/storage/v1/object/public/covers/"

@app.context_processor
def utility_processor():
    def get_cover_url(path):
        """Превръща името на файла в пълен интернет адрес."""
        if not path or str(path).lower() in ["none", "nan", ""]:
            # Ако няма корица, показваме картинка по подразбиране от папка /static/
            return url_for('static', filename='default_cover.png')
        
        # Взимаме само името на файла (в случай че в базата има останал стар път)
        filename = os.path.basename(path)
        # Кодираме го (заради интервали и специални знаци) и добавяме облачния адрес
        return f"{SUPABASE_COVERS_URL}{quote(filename)}"
    
    return dict(get_cover_url=get_cover_url)

# --- ПРЕМАХНАТО: Вече не ни трябва локалният маршрут /covers/ ---

@app.route('/')
def index():
    status = request.args.get('status', 'All')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    books = database.get_books_paginated(status, per_page, offset, search)
    total_books = database.get_total_book_count(status, search)
    total_pages = math.ceil(total_books / per_page)
    
    return render_template('index.html', books=books, current_status=status, 
                           search_query=search, current_page=page, total_pages=total_pages)

@app.route('/book/<int:book_id>')
def book_details(book_id):
    book = database.get_book_by_id(book_id)
    if not book: return "Book not found", 404
    return render_template('book_details.html', book=book)

@app.route('/api/author/<name>')
def api_author(name):
    books = database.get_books_by_author(name)
    return render_template('parts/book_list_mini.html', items=books, title=name)

@app.route('/api/series/<name>')
def api_series(name):
    books = database.get_books_by_series(name)
    return render_template('parts/book_list_mini.html', items=books, title=name, is_series=True)

if __name__ == '__main__':
    # Вече не проверяваме локалната папка, защото всичко е в облака
    print("\n--- CLOUD WEB APP STARTING ---")
    print(f"Database: Supabase Cloud")
    print(f"Images: {SUPABASE_COVERS_URL}")
    print("------------------------------\n")
    
    app.run(debug=True, host='0.0.0.0', port=9999, use_reloader=False)
