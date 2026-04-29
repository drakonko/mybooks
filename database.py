import os
import sys
import psycopg2
import pandas as pd
import logging
import requests
import urllib.parse
import datetime
from psycopg2.extras import RealDictCursor, execute_values
from sqlalchemy import create_engine
from dotenv import load_dotenv

# --- ЗАРЕЖДАНЕ НА НАСТРОЙКИ ---
if getattr(sys, 'frozen', False):
    # Път за .exe файл
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Път за нормално стартиране (скрипт или Render)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, '.env'))

# Настройки за сигурност и URI конструктор
DB_PASS = os.getenv("DB_PASSWORD")
encoded_password = urllib.parse.quote_plus(DB_PASS) if DB_PASS else ""

# Основен URI за psycopg2 (за локалното приложение)
DB_URI = os.getenv("DB_URI") 
if not DB_URI: # Fallback ако липсва целия URI
    DB_URI = f"postgresql://postgres.pvajcaorfmgmdptrtdxh:{encoded_password}@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"

# SQLAlchemy Engine за Pandas (премахва UserWarning и е по-бърз)
# Използваме порт 6543 за стабилна връзка през Pooler
alchemy_uri = f"postgresql+psycopg2://postgres.pvajcaorfmgmdptrtdxh:{encoded_password}@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"
engine = create_engine(alchemy_uri)

def get_db_connection():
    """Свързва се със Supabase през URI с таймаут."""
    return psycopg2.connect(DB_URI, connect_timeout=5)

# --- 1. ИНИЦИАЛИЗАЦИЯ И ПОДДРЪЖКА ---

def create_database():
    """Създава всички необходими таблици в облака."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Таблица Books
        cur.execute('''CREATE TABLE IF NOT EXISTS books
                      (id SERIAL PRIMARY KEY, 
                       title TEXT, author TEXT, rating INTEGER, 
                       status TEXT, date_finished TEXT, isbn13 TEXT, 
                       description_short TEXT, cover_path TEXT, 
                       series_info TEXT, description TEXT, isbn TEXT, 
                       number_of_pages TEXT, average_rating TEXT, 
                       year_published TEXT, genre TEXT, series_number TEXT)''')

        # Таблица Author Works
        cur.execute('''CREATE TABLE IF NOT EXISTS author_works
                      (id SERIAL PRIMARY KEY,
                       author_name TEXT, series_name TEXT, book_title TEXT,
                       series_order TEXT, release_year TEXT, isbn13 TEXT,
                       UNIQUE(author_name, book_title))''')
        
        # Таблица Goals
        cur.execute("CREATE TABLE IF NOT EXISTS goals (year INTEGER PRIMARY KEY, goal INTEGER)")
        
        conn.commit()
    finally:
        cur.close()
        conn.close()

def cleanup_unfinished_book_dates():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE books SET date_finished = '' WHERE status != 'Read' AND date_finished != ''")
        conn.commit()
    except Exception as e:
        logging.error(f"Cleanup Error: {e}")
    finally:
        cur.close()
        conn.close()

def bulk_import_books(data_list):
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        INSERT INTO books (
            title, author, rating, status, date_finished, isbn, 
            description_short, cover_path, series_info, description, 
            isbn13, number_of_pages, average_rating, year_published, 
            genre, series_number
        ) VALUES %s ON CONFLICT DO NOTHING
    """
    try:
        execute_values(cur, query, data_list)
        conn.commit()
        return True, len(data_list)
    except Exception as e:
        conn.rollback()
        return False, 0
    finally:
        cur.close()
        conn.close()

# --- 2. ФУНКЦИИ ЗА ДЕСКТОП ИНТЕРФЕЙС (Pandas) ---

def fetch_all_books():
    """Използва SQLAlchemy Engine за по-стабилна работа с Pandas."""
    try:
        df = pd.read_sql_query("SELECT * FROM books ORDER BY title ASC", engine)
        df.columns = [col.lower() for col in df.columns]
        return df
    except:
        return pd.DataFrame()

def fetch_author_bibliography(name):
    """Търсене в библиографията за десктоп приложението."""
    query = "SELECT * FROM author_works WHERE author_name ILIKE %s ORDER BY release_year DESC"
    try:
        return pd.read_sql_query(query, engine, params=(f"%{name}%",))
    except:
        return pd.DataFrame()

def delete_author_bibliography(author_name):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM author_works WHERE author_name = %s", (author_name,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

def save_author_work(data):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """INSERT INTO author_works (author_name, series_name, book_title, series_order, release_year, isbn13)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (author_name, book_title) DO UPDATE 
                   SET series_name = EXCLUDED.series_name, 
                       series_order = EXCLUDED.series_order, 
                       release_year = EXCLUDED.release_year"""
        cur.execute(query, data)
        conn.commit()
    finally:
        cur.close()
        conn.close()

# --- 3. ЗАПИС И РЕДАКЦИЯ ---

def add_new_book(data):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """INSERT INTO books (title, author, rating, status, date_finished, isbn, 
                   description_short, cover_path, series_info, description, isbn13, 
                   number_of_pages, average_rating, year_published, genre, series_number) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        cur.execute(query, data)
        conn.commit()
        return True
    except Exception as e: 
        logging.error(f"Add Error: {e}")
        return False
    finally: 
        cur.close()
        conn.close()

def update_book_in_db(book_id, data):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            safe_id = int(book_id)
            clean_list = list(data)
            try:
                clean_list[2] = int(float(clean_list[2])) if clean_list[2] else 0
            except: clean_list[2] = 0
            
            query = """UPDATE books SET 
                       title=%s, author=%s, rating=%s, status=%s, date_finished=%s, 
                       isbn=%s, description_short=%s, cover_path=%s, series_info=%s, 
                       description=%s, isbn13=%s, number_of_pages=%s, average_rating=%s, 
                       year_published=%s, genre=%s, series_number=%s 
                       WHERE id=%s"""
            full_params = tuple(clean_list) + (safe_id,)
            cur.execute(query, full_params)
            conn.commit()
            return True
    except Exception as e:
        print(f"Update Crash Prevented: {e}")
        return False
    finally:
        conn.close()

def update_book_status_only(book_id, new_status):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE books SET status = %s WHERE id = %s", (new_status, book_id))
        conn.commit()
    finally:
        cur.close()
        conn.close()

def delete_book(book_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM books WHERE id=%s", (book_id,))
        conn.commit()
        return True
    except: return False
    finally: 
        cur.close()
        conn.close()

# --- 4. WEB APP ФУНКЦИИ (Render) ---

def get_books_paginated(status_filter='All', genre_filter='All', year_filter='All', limit=20, offset=0, search_query=None):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT * FROM books WHERE 1=1"
        params = []

        if status_filter != 'All':
            query += " AND status = %s"; params.append(status_filter)
        if genre_filter != 'All':
            query += " AND genre = %s"; params.append(genre_filter)
        if year_filter != 'All':
            query += " AND year_published = %s"; params.append(year_filter)
        if search_query:
            query += " AND (title ILIKE %s OR author ILIKE %s)"; 
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        
        query += " ORDER BY date_finished DESC NULLS LAST, title ASC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        cur.execute(query, params)
        return cur.fetchall()
    finally: conn.close()

def get_total_book_count(status_filter='All', genre_filter='All', year_filter='All', search_query=None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = "SELECT COUNT(*) FROM books WHERE 1=1"
        params = []
        if status_filter != 'All':
            query += " AND status = %s"; params.append(status_filter)
        if genre_filter != 'All':
            query += " AND genre = %s"; params.append(genre_filter)
        if year_filter != 'All':
            query += " AND year_published = %s"; params.append(year_filter)
        if search_query:
            query += " AND (title ILIKE %s OR author ILIKE %s)"; 
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        cur.execute(query, params)
        return cur.fetchone()[0]
    finally: conn.close()

def get_unique_years_published():
    """Извлича всички налични години на издаване от базата."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT year_published FROM books WHERE year_published != '' AND year_published IS NOT NULL ORDER BY year_published DESC")
        return [row[0] for row in cur.fetchall()]
    finally: conn.close()

def get_book_by_id(book_id):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM books WHERE id = %s", (int(book_id),))
        return cur.fetchone()
    finally: conn.close()

def get_unique_genres():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT genre FROM books WHERE genre IS NOT NULL AND genre != '' ORDER BY genre ASC")
        return [row[0] for row in cur.fetchall()]
    finally: conn.close()

def get_books_by_author_fast(author_name):
    """С планом Б: Търси в библиографията, ако няма - в твоите книги."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT book_title as title, release_year as year, 'Bio' as source FROM author_works WHERE author_name ILIKE %s", (f"%{author_name}%",))
        res = cur.fetchall()
        if not res:
            cur.execute("SELECT title, year_published as year, 'Owned' as source FROM books WHERE author ILIKE %s", (f"%{author_name}%",))
            res = cur.fetchall()
        return res
    finally: conn.close()

# --- 5. СТАТИСТИКИ И ОБЛАЧЕН СИНХРОН ---

def get_2026_read_count():
    """Името остава същото, за да не се чупи кода, но вече брои динамично за текущата година."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Вземаме текущата година от системата (в момента 2026, догодина 2027)
        current_year = datetime.datetime.now().year
        
        # Търсим годината навсякъде в низа, за да хванем и формати като "24.4.2026 г."
        cur.execute("""
            SELECT COUNT(*) FROM books 
            WHERE status = 'Read' 
            AND date_finished LIKE %s
        """, (f"%{current_year}%",))
        
        return cur.fetchone()[0]
    except Exception as e:
        print(f"Грешка в брояча: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def get_yearly_goal(year=2026):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT goal FROM goals WHERE year = %s", (year,))
        row = cur.fetchone()
        return row[0] if row else 50
    except: return 50
    finally:
        cur.close()
        conn.close()

def set_yearly_goal(year, goal):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO goals (year, goal) VALUES (%s, %s) ON CONFLICT (year) DO UPDATE SET goal = EXCLUDED.goal", (year, goal))
        conn.commit()
        return True
    except: return False
    finally:
        cur.close()
        conn.close()

def upload_cover_to_supabase(filename):
    """Качва локален файл в облака."""
    url = f"{os.getenv('SUPABASE_URL')}/storage/v1/object/covers/{filename}"
    headers = {
        "Authorization": f"Bearer {os.getenv('SUPABASE_SERVICE_ROLE_KEY')}",
        "Content-Type": "image/jpeg",
        "x-upsert": "true"
    }
    local_path = os.path.join(BASE_DIR, "covers", filename)
    if not os.path.exists(local_path): return False, "Missing File"
    try:
        with open(local_path, "rb") as f:
            res = requests.put(url, headers=headers, data=f.read())
            return res.status_code == 200, res.text
    except Exception as e: return False, str(e)
