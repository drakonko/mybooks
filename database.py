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
from supabase import create_client, Client

# --- SETUP ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, '.env'))

# Connection strings
DB_PASS = os.getenv("DB_PASSWORD")
encoded_password = urllib.parse.quote_plus(DB_PASS) if DB_PASS else ""
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

DB_URI = os.getenv("DB_URI") 
if not DB_URI:
    DB_URI = f"postgresql://postgres.pvajcaorfmgmdptrtdxh:{encoded_password}@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"

alchemy_uri = f"postgresql+psycopg2://postgres.pvajcaorfmgmdptrtdxh:{encoded_password}@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"
engine = create_engine(alchemy_uri)

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_db_connection():
    return psycopg2.connect(DB_URI, connect_timeout=5)

# --- 1. INITIALIZATION ---

def create_database():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''CREATE TABLE IF NOT EXISTS books
                      (id SERIAL PRIMARY KEY, 
                       title TEXT, author TEXT, rating INTEGER, 
                       status TEXT, date_finished TEXT, isbn13 TEXT, 
                       description_short TEXT, cover_path TEXT, 
                       series_info TEXT, description TEXT, isbn TEXT, 
                       number_of_pages TEXT, average_rating TEXT, 
                       year_published TEXT, genre TEXT, series_number TEXT,
                       ai_recap TEXT, ai_recap_date TEXT)''')

        cur.execute('''CREATE TABLE IF NOT EXISTS author_works
                      (id SERIAL PRIMARY KEY,
                       author_name TEXT, series_name TEXT, book_title TEXT,
                       series_order TEXT, release_year TEXT, isbn13 TEXT,
                       UNIQUE(author_name, book_title))''')
        
        cur.execute("CREATE TABLE IF NOT EXISTS goals (year INTEGER PRIMARY KEY, goal INTEGER)")
        
        cur.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS ai_recap TEXT")
        cur.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS ai_recap_date TEXT")
        
        conn.commit()
    finally:
        cur.close(); conn.close()

# --- 2. AI RETELLING FUNCTIONS ---

def save_book_recap(book_id, text):
    try:
        now = datetime.datetime.now().isoformat()
        supabase.table("books").update({
            "ai_recap": text,
            "ai_recap_date": now
        }).eq("id", book_id).execute()
        return True
    except Exception as e:
        logging.error(f"AI Save Error: {e}"); return False

def get_stored_recap(book_id):
    try:
        response = supabase.table("books").select("ai_recap").eq("id", book_id).execute()
        if response.data and response.data[0].get("ai_recap"):
            return response.data[0]["ai_recap"]
    except Exception as e:
        logging.error(f"AI Fetch Error: {e}")
    return None

# --- 3. DATA FETCHING ---

def fetch_all_books():
    try:
        df = pd.read_sql_query("SELECT * FROM books ORDER BY title ASC", engine)
        df.columns = [col.lower() for col in df.columns]
        return df
    except: return pd.DataFrame()

def fetch_author_bibliography(name):
    query = "SELECT * FROM author_works WHERE author_name ILIKE %s ORDER BY release_year DESC"
    try: return pd.read_sql_query(query, engine, params=(f"%{name}%",))
    except: return pd.DataFrame()

def get_book_by_id(book_id):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM books WHERE id = %s", (int(book_id),))
        return cur.fetchone()
    finally: conn.close()

# --- 4. INSERT / UPDATE / DELETE ---

def add_new_book(data):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """INSERT INTO books (title, author, rating, status, date_finished, isbn, 
                   description_short, cover_path, series_info, description, isbn13, 
                   number_of_pages, average_rating, year_published, genre, series_number) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        cur.execute(query, data); conn.commit(); return True
    except: return False
    finally: cur.close(); conn.close()

def update_book_in_db(book_id, data):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            clean_list = list(data)
            try: clean_list[2] = int(float(clean_list[2]))
            except: clean_list[2] = 0
            query = """UPDATE books SET title=%s, author=%s, rating=%s, status=%s, date_finished=%s, 
                       isbn=%s, description_short=%s, cover_path=%s, series_info=%s, 
                       description=%s, isbn13=%s, number_of_pages=%s, average_rating=%s, 
                       year_published=%s, genre=%s, series_number=%s WHERE id=%s"""
            cur.execute(query, tuple(clean_list) + (int(book_id),))
            conn.commit(); return True
    except: return False
    finally: conn.close()

def update_book_status_only(book_id, new_status, completion_date=None):
    """Quickly updates status and optionally the completion date."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if completion_date:
            cur.execute("UPDATE books SET status = %s, date_finished = %s WHERE id = %s", 
                        (new_status, completion_date, book_id))
        else:
            cur.execute("UPDATE books SET status = %s WHERE id = %s", 
                        (new_status, book_id))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Status Update Error: {e}")
        return False
    finally:
        cur.close(); conn.close()

def delete_book(book_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM books WHERE id=%s", (book_id,))
        conn.commit(); return True
    except: return False
    finally: cur.close(); conn.close()

# --- 5. UTILITIES ---

def get_yearly_goal(year=2026):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT goal FROM goals WHERE year = %s", (year,))
        row = cur.fetchone(); return row[0] if row else 30
    except: return 30
    finally: cur.close(); conn.close()

def set_yearly_goal(year, goal):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO goals (year, goal) VALUES (%s, %s) ON CONFLICT (year) DO UPDATE SET goal = EXCLUDED.goal", (year, goal))
        conn.commit(); return True
    except: return False
    finally: cur.close(); conn.close()

def upload_cover_to_supabase(filename):
    url = f"{SUPABASE_URL}/storage/v1/object/covers/{filename}"
    headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "image/jpeg", "x-upsert": "true"}
    local_path = os.path.join(BASE_DIR, "covers", filename)
    if not os.path.exists(local_path): return False, "Missing"
    try:
        with open(local_path, "rb") as f:
            res = requests.put(url, headers=headers, data=f.read())
            return res.status_code == 200, res.text
    except Exception as e: return False, str(e)

def cleanup_unfinished_book_dates():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE books SET date_finished = '' WHERE status != 'Read' AND date_finished != ''")
        conn.commit()
    finally: cur.close(); conn.close()
