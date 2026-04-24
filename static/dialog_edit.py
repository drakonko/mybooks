import os
import sys
import requests
import shutil
import webbrowser
import urllib.parse
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                             QPushButton, QComboBox, QSpinBox, QDateEdit, 
                             QTextEdit, QHBoxLayout, QLabel, QMessageBox, 
                             QFileDialog, QFrame, QScrollArea, QWidget, QGridLayout,
                             QApplication, QListWidget, QListWidgetItem)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QDate, QSize
import database

# Настройка на папките
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

COVERS_DIR = os.path.join(BASE_DIR, "covers")
if not os.path.exists(COVERS_DIR):
    os.makedirs(COVERS_DIR)

SUPABASE_IMG_URL = "https://pvajcaorfmgmdptrtdxh.supabase.co/storage/v1/object/public/covers/"

class WebCoverSearchDialog(QDialog):
    """Прозорец за избор на корица от Google Books."""
    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Търсене на корица за: {query}")
        self.resize(600, 500)
        self.selected_url = None
        
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(120, 180))
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setSpacing(15)
        
        layout.addWidget(QLabel(f"Резултати за: {query}"))
        layout.addWidget(self.list_widget)
        
        self.btn_select = QPushButton("✅ Избери маркираната корица")
        self.btn_select.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 10px;")
        self.btn_select.clicked.connect(self.accept_selection)
        layout.addWidget(self.btn_select)

        self.fetch_covers(query)

    def fetch_covers(self, query):
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(query)}&maxResults=12"
            res = requests.get(url, timeout=5).json()
            for item in res.get('items', []):
                v = item.get('volumeInfo', {})
                images = v.get('imageLinks', {})
                thumb = images.get('thumbnail') or images.get('smallThumbnail')
                if thumb:
                    thumb = thumb.replace("http://", "https://")
                    title = v.get('title', 'Unknown')
                    
                    item_widget = QListWidgetItem(title[:20] + "...")
                    item_widget.setData(Qt.ItemDataRole.UserRole, thumb)
                    
                    img_data = requests.get(thumb, timeout=3).content
                    pix = QPixmap()
                    pix.loadFromData(img_data)
                    item_widget.setIcon(QIcon(pix.scaled(120, 180, Qt.AspectRatioMode.KeepAspectRatio)))
                    self.list_widget.addItem(item_widget)
        except:
            QMessageBox.warning(self, "Грешка", "Неуспешно свързване с Google Books.")

    def accept_selection(self):
        if self.list_widget.currentItem():
            self.selected_url = self.list_widget.currentItem().data(Qt.ItemDataRole.UserRole)
            self.accept()

class EditBookDialog(QDialog):
    def __init__(self, book_data, parent=None):
        super().__init__(parent)
        self.book_data = book_data
        self.book_id = book_data.get('id')
        self.setWindowTitle(f"Редактиране: {book_data.get('title', 'Нова книга')}")
        self.resize(850, 850) 
        
        self.cover_path_hidden = str(book_data.get('cover_path', ''))
        
        self.init_ui()
        self.load_book_values()

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)

        # --- 1. СЕКЦИЯ КОРИЦА ---
        cover_container = QHBoxLayout()
        self.cover_preview = QLabel("Няма корица")
        self.cover_preview.setFixedSize(180, 270) 
        self.cover_preview.setStyleSheet("border: 2px dashed #bbb; background-color: #f8f9fa; border-radius: 8px;")
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_container.addWidget(self.cover_preview)

        cover_btn_stack = QVBoxLayout()
        cover_btn_stack.setSpacing(8)
        cover_btn_stack.addWidget(QLabel("<b>Опции за корица:</b>"))
        
        self.browse_btn = QPushButton("📁 Локален файл")
        self.web_cover_btn = QPushButton("🌐 Търси в мрежата")
        self.web_cover_btn.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold;")
        self.clear_btn = QPushButton("🗑️ Изчисти корицата")
        
        self.btn_annas = QPushButton("🔍 Anna's Archive")
        self.btn_annas.setStyleSheet("background-color: #5d4037; color: white;")
        self.btn_goodreads = QPushButton("📖 Goodreads")
        self.btn_goodreads.setStyleSheet("background-color: #f4f1ea; color: #382110; border: 1px solid #d6d0c0;")

        for btn in [self.browse_btn, self.web_cover_btn, self.clear_btn, self.btn_annas, self.btn_goodreads]:
            btn.setMinimumHeight(35)
            cover_btn_stack.addWidget(btn)
        
        cover_btn_stack.addStretch()
        cover_container.addLayout(cover_btn_stack)
        content_layout.addLayout(cover_container)

        # --- 2. ОСНОВНА ИНФОРМАЦИЯ ---
        main_info_form = QFormLayout()
        self.crawl_btn = QPushButton("🚀 Deep Crawl (Goodreads Scraper)")
        self.crawl_btn.setStyleSheet("background-color: #372213; color: white; font-weight: bold; padding: 10px;")
        
        self.isbn_in = QLineEdit()
        self.title_in = QLineEdit()
        self.author_in = QLineEdit()
        
        self.meta_btn = QPushButton("🔍 Авто-попълване през ISBN")
        self.meta_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")

        main_info_form.addRow("", self.crawl_btn)
        main_info_form.addRow("ISBN-13:", self.isbn_in)
        main_info_form.addRow("", self.meta_btn)
        main_info_form.addRow("Заглавие:", self.title_in)
        main_info_form.addRow("Автор:", self.author_in)
        content_layout.addLayout(main_info_form)

        # --- 3. ГРИД ---
        grid_frame = QFrame()
        grid_frame.setStyleSheet("QFrame { border: 1px solid #dee2e6; border-radius: 8px; padding: 12px; background: #fff; }")
        grid_layout = QGridLayout(grid_frame)

        self.genre_in = QComboBox()
        self.genre_in.addItems(["Fiction", "Non-Fiction", "Fantasy", "Sci-Fi", "Mystery", "Horror", "History", "Biography", "Uncategorized"])
        self.status_in = QComboBox()
        self.status_in.addItems(["Read", "Currently Reading", "Want to Read", "Did Not Finish"])
        self.rating_in = QSpinBox(); self.rating_in.setRange(0, 5)
        self.pages_in = QLineEdit()
        self.year_in = QLineEdit()
        self.avg_rating_in = QLineEdit()
        self.series_in = QComboBox(); self.series_in.setEditable(True)
        self.series_num_in = QSpinBox(); self.series_num_in.setRange(0, 999)
        self.date_in = QDateEdit(); self.date_in.setCalendarPopup(True)

        grid_layout.addWidget(QLabel("<b>Жанр:</b>"), 0, 0); grid_layout.addWidget(self.genre_in, 0, 1)
        grid_layout.addWidget(QLabel("<b>Година:</b>"), 0, 2); grid_layout.addWidget(self.year_in, 0, 3)
        grid_layout.addWidget(QLabel("<b>Статус:</b>"), 1, 0); grid_layout.addWidget(self.status_in, 1, 1)
        grid_layout.addWidget(QLabel("<b>Общ рейтинг:</b>"), 1, 2); grid_layout.addWidget(self.avg_rating_in, 1, 3)
        grid_layout.addWidget(QLabel("<b>Моят рейтинг:</b>"), 2, 0); grid_layout.addWidget(self.rating_in, 2, 1)
        grid_layout.addWidget(QLabel("<b>Поредица:</b>"), 2, 2); grid_layout.addWidget(self.series_in, 2, 3)
        grid_layout.addWidget(QLabel("<b>Страници:</b>"), 3, 0); grid_layout.addWidget(self.pages_in, 3, 1)
        grid_layout.addWidget(QLabel("<b>№ в поредица:</b>"), 3, 2); grid_layout.addWidget(self.series_num_in, 3, 3)
        grid_layout.addWidget(QLabel("<b>Завършена на:</b>"), 4, 0); grid_layout.addWidget(self.date_in, 4, 1)

        content_layout.addWidget(grid_frame)

        # --- 4. ОПИСАНИЕ ---
        content_layout.addWidget(QLabel("<b>Анотация:</b>"))
        self.desc_in = QTextEdit()
        self.desc_in.setMinimumHeight(180)
        content_layout.addWidget(self.desc_in)

        scroll.setWidget(content_widget)
        outer_layout.addWidget(scroll)

        # --- 5. ФУТЪР ---
        btns = QHBoxLayout()
        save_btn = QPushButton("💾 ЗАПАЗИ И СИНХРОНИЗИРАЙ")
        save_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 12px; font-size: 14px;")
        save_btn.clicked.connect(self.save_data)
        cancel_btn = QPushButton("Отказ")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(save_btn); btns.addWidget(cancel_btn)
        outer_layout.addLayout(btns)

        # Свързване на сигнали
        self.status_in.currentTextChanged.connect(self.toggle_date_field)
        self.browse_btn.clicked.connect(self.browse_local_image)
        self.web_cover_btn.clicked.connect(self.search_covers_online)
        self.clear_btn.clicked.connect(self.clear_current_cover)
        self.btn_annas.clicked.connect(self.search_annas)
        self.btn_goodreads.clicked.connect(self.search_goodreads)
        self.crawl_btn.clicked.connect(self.run_goodreads_crawl)

    def load_book_values(self):
        d = self.book_data
        self.isbn_in.setText(str(d.get('isbn13', d.get('isbn', ''))))
        self.title_in.setText(str(d.get('title', '')))
        self.author_in.setText(str(d.get('author', '')))
        self.genre_in.setCurrentText(str(d.get('genre', 'Uncategorized')))
        self.status_in.setCurrentText(str(d.get('status', 'Want to Read')))
        self.rating_in.setValue(int(d.get('rating', 0)) if d.get('rating') else 0)
        self.pages_in.setText(str(d.get('number_of_pages', '0')))
        self.year_in.setText(str(d.get('year_published', '')))
        self.avg_rating_in.setText(str(d.get('average_rating', '')))
        self.series_in.setCurrentText(str(d.get('series_info', '')))
        self.desc_in.setPlainText(str(d.get('description', '')))
        
        try:
            val = d.get('series_number')
            self.series_num_in.setValue(int(float(val)) if val not in [None, "", "nan"] else 0)
        except: self.series_num_in.setValue(0)

        date_str = str(d.get('date_finished', ''))
        if date_str and len(date_str) > 5:
            self.date_in.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
        else: self.date_in.setDate(QDate.currentDate())
        
        self.toggle_date_field(self.status_in.currentText())
        self.update_cover_preview(self.cover_path_hidden)

    def search_covers_online(self):
        query = f"{self.title_in.text()} {self.author_in.text()}"
        dlg = WebCoverSearchDialog(query, self)
        if dlg.exec():
            img_url = dlg.selected_url
            if img_url:
                try:
                    filename = f"web_{os.urandom(2).hex()}.jpg"
                    dest = os.path.join(COVERS_DIR, filename)
                    res = requests.get(img_url, timeout=5)
                    with open(dest, "wb") as f:
                        f.write(res.content)
                    self.cover_path_hidden = filename
                    self.update_cover_preview(dest)
                except Exception as e:
                    QMessageBox.warning(self, "Грешка", f"Неуспешно изтегляне: {e}")

    def browse_local_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Избери корица", "", "Images (*.jpg *.png)")
        if path:
            filename = f"local_{os.urandom(2).hex()}_{os.path.basename(path)}"
            shutil.copy2(path, os.path.join(COVERS_DIR, filename))
            self.cover_path_hidden = filename
            self.update_cover_preview(os.path.join(COVERS_DIR, filename))

    def clear_current_cover(self):
        self.cover_path_hidden = "default_cover.png"
        self.cover_preview.setText("Изчистено")
        self.cover_preview.setStyleSheet("border: 2px dashed #e74c3c; background-color: #fdf2f2;")

    def update_cover_preview(self, path):
        if not path or "none" in str(path).lower(): return
        filename = os.path.basename(path)
        local_path = os.path.join(COVERS_DIR, filename)
        if os.path.exists(local_path):
            self.cover_preview.setPixmap(QPixmap(local_path).scaled(180, 270, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            try:
                res = requests.get(SUPABASE_IMG_URL + filename, timeout=3)
                if res.status_code == 200:
                    pix = QPixmap(); pix.loadFromData(res.content)
                    self.cover_preview.setPixmap(pix.scaled(180, 270, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            except: pass

    def save_data(self):
        try:
            filename = os.path.basename(self.cover_path_hidden)
            
            # 1. АВТОМАТИЧЕН ОБЛАЧЕН СИНХРОН НА КАРТИНКАТА
            if filename and filename != "default_cover.png":
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                success, msg = database.upload_cover_to_supabase(filename)
                QApplication.restoreOverrideCursor()
                if not success:
                    print(f"Cloud Sync Warning: {msg}")

            # 2. ПОДГОТОВКА НА ДАТАТА (ISO стандарт: 2026-04-24)
            # Това гарантира, че в базата няма да влезе "24.4.2026 г."
            if self.status_in.currentText() == "Read":
                date_str = self.date_in.date().toString("yyyy-MM-dd")
            else:
                date_str = ""

            # 3. СЪБИРАНЕ НА ДАННИТЕ (ТОЧНО 16 ПОЛЕТА)
            data = (
                str(self.title_in.text()).strip(),
                str(self.author_in.text()).strip(),
                int(self.rating_in.value()),
                str(self.status_in.currentText()),
                date_str, # Нашата форматирана дата
                str(self.isbn_in.text()).strip(),
                str(self.desc_in.toPlainText()[:100]).replace("\n", " "), # Кратко описание без нови редове
                filename,
                str(self.series_in.currentText()).strip(),
                str(self.desc_in.toPlainText()),
                str(self.isbn_in.text()).strip(), # isbn13
                str(self.pages_in.text()).strip(),
                str(self.avg_rating_in.text()).strip(),
                str(self.year_in.text()).strip(),
                str(self.genre_in.currentText()),
                str(self.series_num_in.value())
            )
            
            # 4. ЗАПИС В БАЗАТА
            if self.book_id:
                if database.update_book_in_db(self.book_id, data):
                    self.accept()
                else:
                    raise Exception("Грешка при обновяване в Supabase.")
            else:
                if database.add_new_book(data):
                    self.accept()
                else:
                    raise Exception("Грешка при добавяне в Supabase.")
                    
        except Exception as e:
            QApplication.restoreOverrideCursor() # За всеки случай, ако е останал блокиран
            QMessageBox.critical(self, "Грешка", f"Записът се провали: {e}")

    def toggle_date_field(self, status):
        self.date_in.setEnabled(status == "Read")

    def search_annas(self):
        webbrowser.open(f"https://annas-archive.li/search?q={urllib.parse.quote(self.title_in.text())}")

    def search_goodreads(self):
        webbrowser.open(f"https://www.goodreads.com/search?q={urllib.parse.quote(self.title_in.text())}")

    def run_goodreads_crawl(self):
        from logic.goodreads_scraper import scrape_goodreads
        query = self.isbn_in.text() if self.isbn_in.text() else self.title_in.text()
        if not query: return
        self.crawl_btn.setText("⏳ Проучване...")
        QApplication.processEvents()
        info = scrape_goodreads(query)
        if info:
            self.title_in.setText(info.get('title', ''))
            self.author_in.setText(info.get('author', ''))
            self.desc_in.setPlainText(info.get('description', ''))
            self.pages_in.setText(str(info.get('pages', '')))
            self.year_in.setText(str(info.get('year', '')))
            self.series_in.setCurrentText(info.get('series', ''))
            self.series_num_in.setValue(int(info.get('series_num', 0)) if info.get('series_num') else 0)
            self.avg_rating_in.setText(str(info.get('avg_rating', '')))
            QMessageBox.information(self, "Готово", "Данните са извлечени успешно!")
        self.crawl_btn.setText("🚀 Deep Crawl (Goodreads Scraper)")
