import os
import re
import math
import string
import logging
import requests
from io import BytesIO
from PIL import Image
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QMessageBox, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QHBoxLayout, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
import database

# --- CLOUD CONFIG ---
SUPABASE_IMG_URL = "https://pvajcaorfmgmdptrtdxh.supabase.co/storage/v1/object/public/covers/"

def find_kindle_paths():
    """Търси Kindle устройството сред наличните дискове."""
    # Търсим G:\ и след това всички останали букви
    drives = [r"G:\\"] + [f"{d}:\\" for d in string.ascii_uppercase if d != 'G']
    for drive in drives:
        try:
            dp = drive.strip()
            if os.path.exists(dp):
                docs = os.path.join(dp, "documents")
                # Път за Jailbroken Kindle (Screensaver hack)
                ss = os.path.join(dp, "linkss", "screensavers")
                if os.path.exists(docs):
                    return docs, (ss if os.path.exists(ss) else None)
        except: continue
    return None, None

def copy_cover_to_kindle(cover_filename_or_path, book_title):
    """
    Тегли корицата от облака (ако е нужно), преоразмерява я и я качва на Kindle.
    """
    _, ss_dir = find_kindle_paths()
    if not ss_dir: return False, "Screensaver folder not found. Is your Kindle connected and Jailbroken?"
    
    K_WIDTH, K_HEIGHT = 758, 1024 # Стандарт за Paperwhite
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', book_title)
    dest = os.path.join(ss_dir, f"bg_{safe_title}.jpg")
    
    try:
        # 1. Проверяваме дали имаме локален файл или име от облака
        if os.path.exists(cover_filename_or_path):
            img = Image.open(cover_filename_or_path)
        else:
            # Теглим от облака
            filename = os.path.basename(cover_filename_or_path)
            img_url = f"{SUPABASE_IMG_URL}{filename}"
            res = requests.get(img_url, timeout=10)
            if res.status_code != 200:
                return False, "Could not download cover from Supabase."
            img = Image.open(BytesIO(res.content))

        # 2. Обработка на изображението
        with img:
            # Превръщаме в Grayscale (L) за Kindle и ресайзваме
            img = img.convert("L").resize((K_WIDTH, K_HEIGHT), Image.Resampling.LANCZOS)
            img.save(dest, "JPEG", quality=95)
        
        return True, "Cover Synced to Kindle Screensavers!"
    except Exception as e: 
        return False, str(e)

# --- SCANNER THREAD ---

class FolderScannerThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)

    def __init__(self, root_path, db_books):
        super().__init__()
        self.root_path = root_path
        self.db_books = db_books

    def run(self):
        found = []
        exts = ('.azw3', '.mobi', '.azw', '.epub', '.pdf', '.kfx')
        files_to_scan = []
        
        # Обхождаме файловете на Kindle
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if not d.endswith('.sdr')]
            for f in files:
                if f.lower().endswith(exts):
                    files_to_scan.append(os.path.join(root, f))

        total = len(files_to_scan)
        if total == 0:
            self.finished.emit([])
            return

        for i, path in enumerate(files_to_scan):
            filename = os.path.basename(path)
            raw_title = os.path.splitext(filename)[0]
            
            # Почистване на заглавието (Kindle често обръща имената)
            if ", The" in raw_title: raw_title = "The " + raw_title.replace(", The", "")
            if ", A" in raw_title: raw_title = "A " + raw_title.replace(", A", "")

            # Опит за познаване на автора от структурата на папките
            path_parts = path.split(os.sep)
            try:
                author_guess = path_parts[-3] if len(path_parts) >= 3 else "Unknown"
                if author_guess.lower() in ['documents', 'downloads', 'internal storage']:
                    author_guess = "Unknown"
            except:
                author_guess = "Unknown"

            # Сравняваме с базата данни чрез Clean Sets (системата за засичане на дубликати)
            clean_set = set(re.sub(r'[^a-z0-9]', ' ', raw_title.lower()).split())
            match_id, status = None, "New"
            
            for db_b in self.db_books:
                if db_b['clean_set'].intersection(clean_set):
                    intersect = len(db_b['clean_set'].intersection(clean_set))
                    if intersect / max(len(db_b['clean_set']), 1) > 0.6:
                        match_id, status, author_guess = db_b['db_id'], db_b['status'], db_b['author']
                        break
            
            found.append({
                'title': raw_title, 
                'author': author_guess, 
                'status': status, 
                'db_id': match_id, 
                'is_new': match_id is None
            })
            self.progress.emit(int(((i + 1) / total) * 100))
        
        self.finished.emit(found)

# --- DIALOG UI ---

class KindleSyncDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Kindle Device Manager (Cloud Enabled)")
        self.resize(1100, 750)
        self.all_data = []
        self.current_page = 0
        self.page_size = 20
        self.setup_ui()
        self.auto_start_scan()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        header = QHBoxLayout()
        self.status_lbl = QLabel("<b>Scanning Kindle Device...</b>")
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self.auto_start_scan)
        
        self.btn_import = QPushButton("➕ Import New to Cloud")
        self.btn_import.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px 15px;")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self.do_import)

        header.addWidget(self.status_lbl); header.addStretch()
        header.addWidget(self.btn_import); header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Title on Device", "Author", "Library Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Пейджинг
        nav = QHBoxLayout()
        self.btn_prev = QPushButton("⬅️ Prev"); self.btn_next = QPushButton("Next ➡️")
        self.page_info = QLabel("Page 1 of 1")
        self.btn_prev.clicked.connect(self.prev_page); self.btn_next.clicked.connect(self.next_page)
        nav.addStretch(); nav.addWidget(self.btn_prev); nav.addWidget(self.page_info); nav.addWidget(self.btn_next); nav.addStretch()
        layout.addLayout(nav)

    def auto_start_scan(self):
        docs, ss = find_kindle_paths()
        if not docs:
            self.status_lbl.setText("<font color='red'>Kindle device not found on any drive.</font>")
            return
        self.status_lbl.setText(f"<b>Kindle Detected</b> | Screensaver Hack: {'✅' if ss else '❌'}")
        
        # Подготвяме списък от базата за сравнение
        db_list = []
        if hasattr(self.parent_window, 'all_books_df'):
            for _, r in self.parent_window.all_books_df.iterrows():
                t = str(r['title'])
                db_list.append({'orig_title': t, 'db_id': r['id'], 'status': r['status'], 'author': r['author'],
                                'clean_set': set(re.sub(r'[^a-z0-9]', ' ', t.lower()).split())})

        self.progress_bar.show()
        self.scanner = FolderScannerThread(docs, db_list)
        self.scanner.progress.connect(self.progress_bar.setValue)
        self.scanner.finished.connect(self.on_finished)
        self.scanner.start()

    def on_finished(self, data):
        self.all_data = data
        self.progress_bar.hide()
        self.current_page = 0
        self.update_table()
        self.btn_import.setEnabled(any(b['is_new'] for b in data))

    def update_table(self):
        self.table.setRowCount(0)
        total = len(self.all_data)
        total_pages = math.ceil(total / self.page_size) if total > 0 else 1
        start = self.current_page * self.page_size
        page_items = self.all_data[start:start+self.page_size]

        for i, b in enumerate(page_items):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(b['title']))
            self.table.setItem(i, 1, QTableWidgetItem(b['author']))
            item = QTableWidgetItem("➕ New" if b['is_new'] else f"✅ {b['status']}")
            item.setForeground(QColor("#27ae60" if b['is_new'] else "#2980b9"))
            self.table.setItem(i, 2, item)

        self.page_info.setText(f"Page {self.current_page + 1} of {total_pages}")
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < total_pages - 1)

    def next_page(self): self.current_page += 1; self.update_table()
    def prev_page(self): self.current_page -= 1; self.update_table()

    def do_import(self):
        """Импортира новите книги от Kindle директно в облака."""
        new_books = [b for b in self.all_data if b['is_new']]
        
        count = 0
        for b in new_books:
            # Трябва да са точно 16 параметъра за Supabase
            data = (
                b['title'], 
                b['author'], 
                0,                     # rating
                'Want to Read',        # status
                '',                    # date_finished
                '',                    # isbn
                '',                    # description_short
                'default_cover.png',   # cover_path
                '',                    # series_info
                'Imported from Kindle',# description
                '',                    # isbn13
                '0',                   # pages
                '0.0',                 # avg_rating
                '2026',                # year
                'Uncategorized',       # genre
                '0'                    # series_number
            )
            if database.add_new_book(data): 
                count += 1
                
        if count > 0:
            QMessageBox.information(self, "Success", f"Successfully imported {count} books to your Cloud Library!")
            self.parent_window.load_data_from_db()
            self.auto_start_scan()

def run_kindle_sync(parent):
    dialog = KindleSyncDialog(parent)
    dialog.exec()
