import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import pandas as pd
import os
import sys
import logging
import urllib.parse
import datetime
from sqlalchemy import create_engine
from dotenv import load_dotenv

# --- 1. ЗАРЕЖДАНЕ НА НАСТРОЙКИ ---
if getattr(sys, 'frozen', False):
    # Път за .exe файл
    bundle_dir = os.path.dirname(sys.executable)
    load_dotenv(os.path.join(bundle_dir, '.env'))
else:
    # Път за нормално стартиране (скрипт или Render)
    load_dotenv()

# Настройки за сигурност и връзка
DB_PASS = os.getenv("DB_PASSWORD")
encoded_password = urllib.parse.quote_plus(DB_PASS) if DB_PASS else ""

# Основен URI за psycopg2 (ползва Pooler порт 6543 за стабилност)
DB_URI = f"postgresql://postgres.pvajcaorfmgmdptrtdxh:{encoded_password}@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"

# SQLAlchemy URI за Pandas (ползва директен порт 443 за по-бързо четене на таблици)
alchemy_uri = f"postgresql+psycopg2://postgres.pvajcaorfmgmdptrtdxh:{encoded_password}@aws-1-eu-west-3.pooler.supabase.com:443/postgres"
engine = create_engine(alchemy_uri)

def get_db_connection():
    """Основна връзка с облака Supabase."""
    return psycopg2.connect(DB_URI, cursor_factory=RealDictCursor)

# --- 2. ИНИЦИАЛИЗАЦИЯ (СТАРТ) ---

def create_database():
    """Създава необходимите таблици в облака при първо стартиране."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Основна таблица Books
            cur.execute('''CREATE TABLE IF NOT EXISTS books
                          (id SERIAL PRIMARY KEY, title TEXT, author TEXT, rating INTEGER, 
                           status TEXT, date_finished TEXT, isbn13 TEXT, description_short TEXT, 
                           cover_path TEXT, series_info TEXT, description TEXT, isbn TEXT, 
                           number_of_pages TEXT, average_rating TEXT, year_published TEXT,
                           genre TEXT, series_number TEXT)''')
            
            # Таблица за авторски библиографии
            cur.execute('''CREATE TABLE IF NOT EXISTS author_works
                          (id SERIAL PRIMARY KEY, author_name TEXT, series_name TEXT, book_title TEXT,
                           series_order TEXT, release_year TEXT, isbn13 TEXT,
                           UNIQUE(author_name, book_title))''')
            
            # Таблица за годишни цели
            cur.execute('''CREATE TABLE IF NOT EXISTS yearly_goals
                          (year INTEGER PRIMARY KEY, goal_count INTEGER)''')
        conn.commit()
    finally:
        conn.close()

# --- 3. СТАТИСТИКИ И ЦЕЛИ ---

def get_yearly_goal(year=None):
    if year is None: year = datetime.datetime.now().year
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT goal_count FROM yearly_goals WHERE year = %s", (int(year),))
        res = cur.fetchone()
        return res['goal_count'] if res else 50
    except: return 50
    finally: conn.close()

def set_yearly_goal(year, count):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO yearly_goals (year, goal_count) VALUES (%s, %s)
                           ON CONFLICT (year) DO UPDATE SET goal_count = EXCLUDED.goal_count""", 
                        (int(year), int(count)))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def get_2026_read_count():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as count FROM books WHERE status = 'Read' AND date_finished LIKE '2026-%%'")
        res = cur.fetchone()
        return res['count'] if res else 0
    finally: conn.close()

# --- 4. ДЕСКТОП ОПЕРАЦИИ (Pandas & CRUD) ---

def fetch_all_books():
    """Зарежда всичко в Pandas DataFrame за главната таблица."""
    return pd.read_sql_query("SELECT * FROM books ORDER BY title ASC", engine)

def add_new_book(data):
    """Добавя нова книга (изисква точно 16 параметъра)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """INSERT INTO books (title, author, rating, status, date_finished, isbn, 
                       description_short, cover_path, series_info, description, isbn13, 
                       number_of_pages, average_rating, year_published, genre, series_number) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(query, data)
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Грешка при добавяне: {e}")
        return False
    finally: conn.close()

def update_book_in_db(book_id, data):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """UPDATE books SET title=%s, author=%s, rating=%s, status=%s, date_finished=%s, 
                       isbn=%s, description_short=%s, cover_path=%s, series_info=%s, description=%s, 
                       isbn13=%s, number_of_pages=%s, average_rating=%s, year_published=%s, 
                       genre=%s, series_number=%s WHERE id=%s"""
            cur.execute(query, data + (int(book_id),))
        conn.commit()
    finally: conn.close()

def update_book_status(book_id, new_status):
    """Бързо обновяване на статус + автоматична дата."""
    conn = get_db_connection()
    try:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d") if new_status == "Read" else ""
        with conn.cursor() as cur:
            cur.execute("UPDATE books SET status = %s, date_finished = %s WHERE id = %s", 
                        (new_status, date_str, int(book_id)))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def delete_book(book_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM books WHERE id=%s", (int(book_id),))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

# --- 5. МАСОВ ИМПОРТ И АВТОРИ ---

def bulk_import_books(data_list):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """INSERT INTO books (title, author, rating, status, date_finished, isbn, 
                       description_short, cover_path, series_info, description, isbn13, 
                       number_of_pages, average_rating, year_published, genre, series_number) 
                       VALUES %s ON CONFLICT DO NOTHING"""
            execute_values(cur, query, data_list)
        conn.commit()
        return True, len(data_list)
    except Exception as e:
        logging.error(f"Bulk Error: {e}")
        return False, 0
    finally: conn.close()

def save_author_work(data):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """INSERT INTO author_works (author_name, series_name, book_title, series_order, release_year, isbn13)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (author_name, book_title) DO UPDATE 
                       SET series_name=EXCLUDED.series_name, series_order=EXCLUDED.series_order, release_year=EXCLUDED.release_year"""
            cur.execute(query, data)
        conn.commit()
    finally: conn.close()

def fetch_author_bibliography(name):
    query = "SELECT * FROM author_works WHERE author_name ILIKE %s ORDER BY release_year DESC"
    return pd.read_sql_query(query, engine, params=(f"%{name}%",))

# --- 6. WEB APP ФУНКЦИИ (Render) ---

def get_books_paginated(status_filter='All', genre_filter='All', limit=20, offset=0, search_query=None):
    """Позволява филтриране по статус И по жанр едновременно."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = "SELECT * FROM books WHERE 1=1"
        params = []
        if status_filter != 'All':
            query += " AND status = %s"
            params.append(status_filter)
        if genre_filter != 'All':
            query += " AND genre = %s"
            params.append(genre_filter)
        if search_query:
            query += " AND (title ILIKE %s OR author ILIKE %s)"
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        
        query += " ORDER BY date_finished DESC NULLS LAST, title ASC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally: conn.close()

def get_total_book_count(status_filter='All', genre_filter='All', search_query=None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = "SELECT COUNT(*) FROM books WHERE 1=1"
        params = []
        if status_filter != 'All':
            query += " AND status = %s"; params.append(status_filter)
        if genre_filter != 'All':
            query += " AND genre = %s"; params.append(genre_filter)
        if search_query:
            query += " AND (title ILIKE %s OR author ILIKE %s)"; params.extend([f'%{search_query}%', f'%{search_query}%'])
        cur.execute(query, params)
        res = cur.fetchone()
        return res['count'] if res else 0
    finally: conn.close()

def get_unique_genres():
    """Зарежда всички налични жанрове в базата за уеб менюто."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT genre FROM books WHERE genre IS NOT NULL AND genre != '' ORDER BY genre ASC")
        return [row['genre'] for row in cur.fetchall()]
    finally: conn.close()

def get_book_by_id(book_id):
    """Поправя грешка 500 на Render - зарежда детайлите на книгата."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM books WHERE id = %s", (int(book_id),))
        return cur.fetchone()
    finally: conn.close()
