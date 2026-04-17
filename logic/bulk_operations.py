import os
import time
import requests
import urllib.parse
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QLabel, 
                             QMessageBox, QApplication, QFrame)
from supabase import create_client
import database

# --- CLOUD CONFIG ---
SUPABASE_URL = "https://pvajcaorfmgmdptrtdxh.supabase.co"
# Използваме Secret Key за масови качвания
SUPABASE_KEY = "sb_secret_A7wVlHjhTkJBHhsKVJmh3g_wInblMKv"

class BulkRepairDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Library Maintenance (Cloud Sync)")
        self.resize(450, 350)
        
        # Инициализираме Supabase клиента
        self.sb_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Секция 1: Изчистване (Reset)
        reset_frame = QFrame()
        reset_frame.setStyleSheet("background: #fff5f5; border: 1px solid #feb2b2; border-radius: 8px;")
        reset_lay = QVBoxLayout(reset_frame)
        reset_lay.addWidget(QLabel("<b>Dangerous Area: Reset Cloud Paths</b>"))
        
        self.btn_clear = QPushButton("🗑️ Clear All Cover Paths in DB")
        self.btn_clear.setStyleSheet("background-color: #e53e3e; color: white; font-weight: bold; padding: 10px;")
        self.btn_clear.clicked.connect(self.clear_all_cover_paths)
        reset_lay.addWidget(self.btn_clear)
        layout.addWidget(reset_frame)

        layout.addSpacing(20)

        # Секция 2: Ремонт (Repair)
        repair_frame = QFrame()
        repair_frame.setStyleSheet("background: #f0fff4; border: 1px solid #9ae6b4; border-radius: 8px;")
        repair_lay = QVBoxLayout(repair_frame)
        repair_lay.addWidget(QLabel("<b>Cloud Repair: High-Res Auto-Download</b>"))
        repair_lay.addWidget(QLabel("<small>Downloads missing covers and uploads them to Supabase Storage.</small>"))
        
        self.btn_repair = QPushButton("🚀 Run Cloud High-Res Repair")
        self.btn_repair.setStyleSheet("background-color: #38a169; color: white; font-weight: bold; padding: 10px;")
        self.btn_repair.clicked.connect(self.run_repair)
        repair_lay.addWidget(self.btn_repair)
        layout.addWidget(repair_frame)

    def clear_all_cover_paths(self):
        """Изчиства пътищата към кориците в облачната база данни."""
        confirm = QMessageBox.question(
            self, "Confirm Reset", 
            "This will remove the link to covers for ALL books in the cloud database. The images will remain in Storage, but won't show up. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                conn = database.get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("UPDATE books SET cover_path = ''")
                conn.commit()
                conn.close()
                
                QMessageBox.information(self, "Success", "All cover paths have been cleared in the cloud.")
                self.parent_window.load_data_from_db()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Database error: {e}")

    def run_repair(self):
        """Търси липсващи корици в Google Books и ги качва в Supabase Storage."""
        df = self.parent_window.all_books_df
        # Търсим книги без корица или без описание
        to_fix = df[(df['cover_path'] == "") | (df['cover_path'].isna()) | (df['description'] == "") | (df['description'].isna())]
        
        if to_fix.empty:
            QMessageBox.information(self, "Library Clean", "All books have covers and descriptions!")
            return

        confirm = QMessageBox.question(self, "Start Repair", f"Found {len(to_fix)} books to repair. Start cloud upload process?")
        if confirm != QMessageBox.StandardButton.Yes: return

        success_count = 0
        
        for i, (_, book) in enumerate(to_fix.iterrows()):
            # Визуална обратна връзка
            self.btn_repair.setText(f"⏳ Processing {i+1}/{len(to_fix)}...")
            QApplication.processEvents()
            
            try:
                # 1. Търсене в Google Books
                search_query = f"intitle:{book['title']}+inauthor:{book['author']}"
                url = f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(search_query)}&maxResults=1"
                res = requests.get(url, timeout=10).json()

                if "items" in res:
                    info = res["items"][0]["volumeInfo"]
                    full_desc = info.get("description", book['description'] or "No description available.")
                    image_links = info.get("imageLinks", {})
                    
                    # Избираме най-високото качество
                    img_url = (image_links.get("extraLarge") or image_links.get("large") or 
                               image_links.get("medium") or image_links.get("thumbnail"))

                    new_cover_name = book['cover_path']

                    if img_url:
                        # 2. Подобряваме резолюцията на линка
                        img_url = img_url.replace("http://", "https://")
                        if "zoom=1" in img_url: img_url = img_url.replace("zoom=1", "zoom=2")
                        
                        # 3. Сваляме изображението в паметта
                        img_data = requests.get(img_url, timeout=10).content
                        
                        # 4. Качваме директно в Supabase Storage
                        new_cover_name = f"auto_{book['id']}_{os.urandom(2).hex()}.jpg"
                        self.sb_client.storage.from_("covers").upload(new_cover_name, img_data)
                    
                    # 5. Обновяваме записа в Postgres (всички 16 полета)
                    updated_data = (
                        str(book['title']), 
                        str(book['author']), 
                        int(book['rating'] or 0), 
                        str(book['status']), 
                        str(book['date_finished'] or ""), 
                        str(book['isbn'] or ""), 
                        str(full_desc[:150]), # description_short
                        str(new_cover_name), # Новият облачен файл
                        str(book['series_info'] or ""), 
                        str(full_desc), 
                        str(book['isbn13'] or ""), 
                        str(book['number_of_pages'] or ""), 
                        str(book['average_rating'] or ""), 
                        str(book['year_published'] or ""), 
                        str(book['genre'] or "Uncategorized"),
                        str(book['series_number'] or "0") # 16-тото поле
                    )
                    
                    database.update_book_in_db(book['id'], updated_data)
                    success_count += 1
                
                # Малка пауза, за да не ни блокира Google API
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error repairing book {book['id']}: {e}")

        self.btn_repair.setText("🚀 Run Cloud High-Res Repair")
        self.parent_window.load_data_from_db()
        QMessageBox.information(self, "Repair Finished", f"Successfully repaired and uploaded {success_count} book covers.")

def run_bulk_update_logic(parent):
    """Входна точка от main.py"""
    dialog = BulkRepairDialog(parent)
    dialog.exec()
