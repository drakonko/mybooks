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

# --- ЗАРЕЖДАНЕ НА НАСТРОЙКИ ---
# Тази част е критична за твоето .exe
if getattr(sys, 'frozen', False):
    # Ако работим като .exe, търсим .env в същата папка
    bundle_dir = os.path.dirname(sys.executable)
    load_dotenv(os.path.join(bundle_dir, '.env'))
else:
    # Ако работим като скрипт, зареждаме нормално
    load_dotenv()

DB_PASS = os.getenv("DB_PASSWORD")
# Ако паролата съдържа специални символи, я кодираме за URL-а
encoded_password = urllib.parse.quote_plus(DB_PASS) if DB_PASS else ""

# Твоят адрес за връзка (вече ползва променливите от .env)
DB_URI = f"postgresql://postgres.pvajcaorfmgmdptrtdxh:{encoded_password}@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"

# SQLAlchemy Engine за Pandas (премахва досадното UserWarning)
alchemy_uri = f"postgresql+psycopg2://postgres.pvajcaorfmgmdptrtdxh:{encoded_password}@aws-1-eu-west-3.pooler.supabase.com:443/postgres"
engine = create_engine(alchemy_uri)

def get_db_connection():
    """Основна връзка с облака."""
    return psycopg2.connect(DB_URI, cursor_factory=RealDictCursor)

# --- 1. СТАТИСТИКИ И ЦЕЛИ ---

def get_yearly_goal(year=None):
    """Връща целта за конкретна година. Ако няма такава, връща 12 по подразбиране."""
    if year is None:
        year = datetime.datetime.now().year
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT goal_count FROM yearly_goals WHERE year = %s", (int(year),))
        res = cur.fetchone()
        return res['goal_count'] if res else 12
    except:
        return 12
    finally:
        conn.close()

def set_yearly_goal(year, count):
    """Записва или обновява целта за дадена година в облака."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """
                INSERT INTO yearly_goals (year, goal_count) 
                VALUES (%s, %s) 
                ON CONFLICT (year) DO UPDATE SET goal_count = EXCLUDED.goal_count
            """
            cur.execute(query, (int(year), int(count)))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error setting goal: {e}")
        return False
    finally:
        conn.close() 

def get_2026_read_count():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as count FROM books WHERE status = 'Read' AND date_finished LIKE '2026-%%'")
        res = cur.fetchone()
        return res['count'] if res else 0
    except Exception as e:
        logging.error(f"Goal Count Error: {e}")
        return 0
    finally: conn.close()

# --- 2. ФУНКЦИИ ЗА ДАННИ (Pandas/Desktop) ---

def fetch_all_books():
    return pd.read_sql_query("SELECT * FROM books ORDER BY title ASC", engine)

def fetch_author_bibliography(name):
    query = "SELECT * FROM author_works WHERE author_name ILIKE %s ORDER BY release_year DESC"
    return pd.read_sql_query(query, engine, params=(name,))

def add_new_book(data):
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
        logging.error(f"Add Book Error: {e}")
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
    """Бързо обновяване на статус (ползва се в Details прозореца)."""
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

# --- 3. МАСОВИ ОПЕРАЦИИ ---

def bulk_import_books(data_list):
    """Турбо импорт за Goodreads CSV."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """
                INSERT INTO books (
                    title, author, rating, status, date_finished, isbn, 
                    description_short, cover_path, series_info, description, 
                    isbn13, number_of_pages, average_rating, year_published, 
                    genre, series_number
                ) VALUES %s
                ON CONFLICT DO NOTHING
            """
            execute_values(cur, query, data_list)
        conn.commit()
        return True, len(data_list)
    except Exception as e:
        logging.error(f"Bulk Import Error: {e}")
        return False, 0
    finally: conn.close()

def save_author_work(data):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """
            INSERT INTO author_works (author_name, series_name, book_title, series_order, release_year, isbn13)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (author_name, book_title) DO UPDATE SET
            series_name = EXCLUDED.series_name, series_order = EXCLUDED.series_order,
            release_year = EXCLUDED.release_year, isbn13 = EXCLUDED.isbn13
            """
            cur.execute(query, data)
        conn.commit()
    finally: conn.close()

# --- 4. WEB APP ФУНКЦИИ ---

def get_books_paginated(status_filter='All', limit=20, offset=0, search_query=None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = "SELECT * FROM books WHERE 1=1"
        params = []
        if status_filter and status_filter != 'All':
            query += " AND status = %s"
            params.append(status_filter)
        if search_query:
            query += " AND (title ILIKE %s OR author ILIKE %s)"
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        query += " ORDER BY date_finished DESC NULLS LAST, title ASC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally: conn.close()

def get_total_book_count(status_filter='All', search_query=None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = "SELECT COUNT(*) FROM books WHERE 1=1"
        params = []
        if status_filter and status_filter != 'All':
            query += " AND status = %s"
            params.append(status_filter)
        if search_query:
            query += " AND (title ILIKE %s OR author ILIKE %s)"
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        cur.execute(query, params)
        res = cur.fetchone()
        return res['count'] if res else 0
    finally: conn.close()

# --- 5. INITIALIZATION ---

def create_database():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS books
                          (id SERIAL PRIMARY KEY, title TEXT, author TEXT, rating INTEGER, 
                           status TEXT, date_finished TEXT, isbn13 TEXT, description_short TEXT, 
                           cover_path TEXT, series_info TEXT, description TEXT, isbn TEXT, 
                           number_of_pages TEXT, average_rating TEXT, year_published TEXT,
                           genre TEXT, series_number TEXT)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS author_works
                          (id SERIAL PRIMARY KEY, author_name TEXT, series_name TEXT, book_title TEXT,
                           series_order TEXT, release_year TEXT, isbn13 TEXT,
                           UNIQUE(author_name, book_title))''')
        conn.commit()
    finally: conn.close()

def cleanup_unfinished_book_dates():
    """Изчиства датата на завършване за книги, които не са със статус 'Read'."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Премахваме датата за всичко, което не е прочетено
            cur.execute("UPDATE books SET date_finished = '' WHERE status != 'Read' AND date_finished != ''")
        conn.commit()
    except Exception as e:
        logging.error(f"Cleanup Error: {e}")
    finally:
        conn.close()
