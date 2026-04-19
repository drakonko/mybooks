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
            # Ако няма корица, показваме картинка по подразбиране
            return url_for('static', filename='default_cover.png')
        
        # Взимаме само името на файла
        filename = os.path.basename(path)
        # Кодираме го и добавяме облачния адрес
        return f"{SUPABASE_COVERS_URL}{quote(filename)}"
    
    return dict(get_cover_url=get_cover_url)

@app.route('/')
def index():
    # 1. Взимаме параметрите от URL адреса
    status = request.args.get('status', 'All')
    genre = request.args.get('genre', 'All') # НОВО: Филтър за жанр
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    
    per_page = 20
    offset = (page - 1) * per_page
    
    # 2. Извикваме обновените функции от database.py с новия параметър genre
    books = database.get_books_paginated(status, genre, per_page, offset, search)
    total_books = database.get_total_book_count(status, genre, search)
    
    # 3. Взимаме списък с всички налични жанрове за падащото меню
    all_genres = database.get_unique_genres()
    
    total_pages = math.ceil(total_books / per_page)
    
    return render_template('index.html', 
                           books=books, 
                           current_status=status, 
                           current_genre=genre,   # Изпращаме текущия избран жанр
                           all_genres=all_genres, # Изпращаме списъка с всички жанрове
                           search_query=search, 
                           current_page=page, 
                           total_pages=total_pages)

@app.route('/book/<int:book_id>')
def book_details(book_id):
    book = database.get_book_by_id(book_id)
    if not book: return "Book not found", 404
    return render_template('book_details.html', book=book)

@app.route('/api/author/<name>')
def api_author(name):
    # Вземаме данните от базата
    df = database.fetch_author_bibliography(name)
    
    # КРИТИЧНО: Превръщаме DataFrame в списък от речници
    books = df.to_dict('records')
    
    if not books:
        return "<p class='text-muted p-3'>Няма открити допълнителни творби за този автор.</p>"
        
    return render_template('parts/book_list_mini.html', items=books, title=name)

@app.route('/api/series/<name>')
def api_series(name):
    # Тук също е по-добре да филтрираме директно през базата или да подсигурим речниците
    all_books_df = database.fetch_all_books()
    
    # Филтрираме внимателно (case-insensitive и без интервали)
    series_books = all_books_df[all_books_df['series_info'].str.strip() == name.strip()].to_dict('records')
    
    if not series_books:
        return "<p class='text-muted p-3'>Няма други книги от тази поредица.</p>"
        
    return render_template('parts/book_list_mini.html', items=series_books, title=name, is_series=True)

if __name__ == '__main__':
    print("\n--- CLOUD WEB APP STARTING ---")
    print(f"Database: Supabase Cloud")
    print(f"Images: {SUPABASE_COVERS_URL}")
    print("------------------------------\n")
    
    # На Render портът се подава автоматично, но за локални тестове ползваме 9999
    port = int(os.environ.get("PORT", 9999))
    app.run(debug=True, host='0.0.0.0', port=port)
