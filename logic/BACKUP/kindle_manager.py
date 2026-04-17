import os
import re
import math
import string
import logging
from PIL import Image
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QMessageBox, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QHBoxLayout, QProgressBar, 
                             QButtonGroup, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
import database

# --- HELPER FUNCTIONS ---

def find_kindle_paths():
    """Prioritizes G:\ and safely checks for folders."""
    drives = [r"G:\\"] + [f"{d}:\\" for d in string.ascii_uppercase if d != 'G']
    for drive in drives:
        try:
            drive_path = drive.strip()
            if os.path.exists(drive_path):
                docs = os.path.join(drive_path, "documents")
                ss = os.path.join(drive_path, "linkss", "screensavers")
                if os.path.exists(docs):
                    return docs, (ss if os.path.exists(ss) else None)
        except: continue
    return None, None

def copy_cover_to_kindle(source_cover_path, book_title):
    _, ss_dir = find_kindle_paths()
    if not ss_dir: return False, "Screensaver folder not found."
    K_WIDTH, K_HEIGHT = 758, 1024
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', book_title)
    dest = os.path.join(ss_dir, f"bg_{safe_title}.jpg")
    try:
        with Image.open(source_cover_path) as img:
            img = img.convert("L").resize((K_WIDTH, K_HEIGHT), Image.Resampling.LANCZOS)
            img.save(dest, "JPEG", quality=95)
        return True, "Cover Synced!"
    except Exception as e: return False, str(e)

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
            raw_name = os.path.splitext(filename)[0]
            
            # --- AUTHOR DETECTION LOGIC ---
            # 1. Try folder structure: documents/Author/Title/file.azw3
            path_parts = path.split(os.sep)
            # documents is at -4 or -3 depending on depth. We want the one after 'documents'
            try:
                doc_idx = path_parts.index("documents")
                author = path_parts[doc_idx + 1] if len(path_parts) > doc_idx + 1 else "Unknown"
                # If author is just the filename again, it's a flat structure
                if author == filename or author == raw_name:
                    author = "Unknown"
            except:
                author = "Unknown"

            # 2. Try Filename split if still Unknown (e.g. "Author - Title.azw3")
            if author == "Unknown" and " - " in raw_name:
                parts = raw_name.split(" - ", 1)
                author = parts[0].strip()
                raw_name = parts[1].strip()

            clean_name = set(re.sub(r'[^a-z0-9]', ' ', raw_name.lower()).split())
            match_id, status = None, "New"
            
            for db_b in self.db_books:
                if db_b['clean_set'].intersection(clean_name):
                    intersect = len(db_b['clean_set'].intersection(clean_name))
                    if intersect / max(len(db_b['clean_set']), 1) > 0.6:
                        match_id, status, author = db_b['db_id'], db_b['status'], db_b['author']
                        break
            
            found.append({'title': raw_name, 'author': author, 'status': status, 'db_id': match_id, 'is_new': match_id is None})
            self.progress.emit(int(((i + 1) / total) * 100))
        
        self.finished.emit(found)

# --- DIALOG UI ---

class KindleSyncDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Kindle Device Manager")
        self.resize(1100, 900) # Taller window
        self.all_data = []
        self.current_page = 0
        self.page_size = 20 # 20 books per page
        self.setup_ui()
        self.auto_start_scan()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- HEADER (Refresh and Import at the top) ---
        header = QHBoxLayout()
        self.status_lbl = QLabel("<b>Searching...</b>")
        
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self.auto_start_scan)
        
        self.btn_import = QPushButton("➕ Import New Books")
        self.btn_import.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px 15px;")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self.do_import)

        header.addWidget(self.status_lbl)
        header.addStretch()
        header.addWidget(self.btn_import)
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Title on Kindle", "Author", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # --- PAGINATION CONTROLS (At the bottom) ---
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("⬅️ Previous")
        self.btn_next = QPushButton("Next ➡️")
        self.page_info = QLabel("Page 1 of 1")
        
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next.clicked.connect(self.next_page)
        
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.page_info)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addStretch()
        layout.addLayout(nav_layout)

    def auto_start_scan(self):
        docs, ss = find_kindle_paths()
        if not docs:
            self.status_lbl.setText("<font color='red'>Kindle not detected.</font>")
            return

        self.status_lbl.setText(f"<b>Kindle Found (G:)</b> | Screensaver Folder: {'✅' if ss else '❌'}")
        
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
        
        new_exists = any(b['is_new'] for b in data)
        self.btn_import.setEnabled(new_exists)

    def update_table(self):
        self.table.setRowCount(0)
        total = len(self.all_data)
        total_pages = math.ceil(total / self.page_size) if total > 0 else 1
        
        start = self.current_page * self.page_size
        end = start + self.page_size
        page_items = self.all_data[start:end]

        for i, b in enumerate(page_items):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(b['title']))
            self.table.setItem(i, 1, QTableWidgetItem(b['author']))
            
            status_item = QTableWidgetItem("➕ New" if b['is_new'] else f"✅ {b['status']}")
            status_item.setForeground(QColor("#27ae60" if b['is_new'] else "#2980b9"))
            self.table.setItem(i, 2, status_item)

        self.page_info.setText(f"Page {self.current_page + 1} of {total_pages}")
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < total_pages - 1)

    def next_page(self): self.current_page += 1; self.update_table()
    def prev_page(self): self.current_page -= 1; self.update_table()

    def do_import(self):
        new_books = [b for b in self.all_data if b['is_new']]
        formatted = [(b['title'], b['author'], 0, 'Want to Read', '', '', '', 'default_cover.png', '', 'Kindle Sync', '', '0', '0.0', '2026', 'Uncategorized', '') for b in new_books]
        
        count = 0
        for b in formatted:
            if database.add_new_book(b): count += 1
        
        if count > 0:
            QMessageBox.information(self, "Success", f"Imported {count} books!")
            self.parent_window.load_data_from_db()
            self.auto_start_scan()

def run_kindle_sync(parent):
    dialog = KindleSyncDialog(parent)
    dialog.exec()
