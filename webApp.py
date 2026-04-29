import os
import math
import database
from flask import Flask, render_template, request, url_for, redirect
from urllib.parse import quote
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret_reading_key_2026"

# Твоят нов публичен адрес за кориците в Supabase
SUPABASE_COVERS_URL = "https://pvajcaorfmgmdptrtdxh.supabase.co/storage/v1/object/public/covers/"

@app.context_processor
def utility_processor():
    def get_cover_url(path):
        """Превръща името на файла в пълен интернет адрес."""
        if not path or str(path).lower() in ["none", "nan", ""]:
            return url_for('static', filename='default_cover.png')
        
        filename = os.path.basename(path)
        return f"{SUPABASE_COVERS_URL}{quote(filename)}"
    
    return dict(get_cover_url=get_cover_url)

@app.route('/')
def index():
    status = request.args.get('status', 'All')
    genre = request.args.get('genre', 'All')
    year = request.args.get('year', 'All')
    search = request.args.get('search', '')
    page = int(request.args.get('page', 1))
    
    per_page = 20
    offset = (page - 1) * per_page

    books = database.get_books_paginated(status, genre, year, per_page, offset, search)
    total_books = database.get_total_book_count(status, genre, year, search)
    
    return render_template('index.html', 
                           books=books,
                           current_status=status,
                           current_genre=genre,
                           current_year=year,
                           search_query=search,
                           genres=database.get_unique_genres(),
                           years=database.get_unique_years_published(),
                           current_page=page,
                           total_pages=(total_books + per_page - 1) // per_page,
                           total_books=total_books)

@app.route('/book/<int:book_id>')
def book_details(book_id):
    book = database.get_book_by_id(book_id)
    if not book: return "Book not found", 404
    author_books = database.get_books_by_author_fast(book['author'])
    return render_template('book_details.html', book=book, author_books=author_books)

# --- НОВИ МАРШРУТИ ЗА УПРАВЛЕНИЕ ---

@app.route('/book/<int:book_id>/rate', methods=['POST'])
def rate_book(book_id):
    """Обновява оценката на книгата."""
    rating = request.form.get('rating')
    if rating:
        conn = database.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE books SET rating = %s WHERE id = %s", (int(rating), book_id))
            conn.commit()
        finally:
            cur.close()
            conn.close()
    # request.referrer пази всички филтри в URL адреса
    return redirect(request.referrer or url_for('book_details', book_id=book_id))

@app.route('/book/<int:book_id>/mark_as_read', methods=['POST'])
def mark_as_read(book_id):
    """Маркира книгата като прочетена с днешна дата."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = database.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE books SET status = 'Read', date_finished = %s WHERE id = %s", (today, book_id))
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return redirect(request.referrer or url_for('book_details', book_id=book_id))

# --- API МАРШРУТИ ---

@app.route('/api/author/<name>')
def api_author(name):
    books = database.get_books_by_author(name)
    return render_template('parts/book_list_mini.html', items=books, title=name)

@app.route('/api/series/<name>')
def api_series(name):
    books = database.get_books_by_series(name)
    return render_template('parts/book_list_mini.html', items=books, title=name, is_series=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 9999))
    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)
