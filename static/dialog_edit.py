import os
import sys
import requests
import shutil
import webbrowser
import urllib.parse
import pandas as pd # Добавено за обработка на поредиците
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
                    pix = QPixmap(); pix.loadFromData(img_data)
                    item_widget.setIcon(QIcon(pix.scaled(120, 180, Qt.AspectRatioMode.KeepAspectRatio)))
                    self.list_widget.addItem(item_widget)
        except:
            pass

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
        
        self.cover_path_hidden = str(book_data.get('cover_path', 'default_cover.png'))
        
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

        # --- 1. КОРИЦА ---
        cover_container = QHBoxLayout()
        self.cover_preview = QLabel("Няма корица")
        self.cover_preview.setFixedSize(180, 270) 
        self.cover_preview.setStyleSheet("border: 2px dashed #bbb; background-color: #f8f9fa; border-radius: 8px;")
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_container.addWidget(self.cover_preview)

        cover_btn_stack = QVBoxLayout()
        self.browse_btn = QPushButton("📁 Локален файл")
        self.web_cover_btn = QPushButton("🌐 Търси в мрежата")
        self.web_cover_btn.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold;")
        self.clear_btn = QPushButton("🗑️ Изчисти")
        
        for btn in [self.browse_btn, self.web_cover_btn, self.clear_btn]:
            btn.setMinimumHeight(35)
            cover_btn_stack.addWidget(btn)
        
        cover_btn_stack.addStretch()
        cover_container.addLayout(cover_btn_stack)
        content_layout.addLayout(cover_container)

        # --- 2. ОСНОВНА ИНФОРМАЦИЯ ---
        form = QFormLayout()
        self.crawl_btn = QPushButton("🚀 Deep Crawl (Goodreads)")
        self.crawl_btn.setStyleSheet("background-color: #372213; color: white; font-weight: bold; padding: 10px;")
        
        self.isbn_in = QLineEdit()
        self.title_in = QLineEdit()
        self.author_in = QLineEdit()
        
        form.addRow("", self.crawl_btn)
        form.addRow("ISBN-13:", self.isbn_in)
        form.addRow("Заглавие *:", self.title_in)
        form.addRow("Автор *:", self.author_in)
        content_layout.addLayout(form)

        # --- 3. ГРИД ДЕТАЙЛИ ---
        grid_frame = QFrame()
        grid_frame.setStyleSheet("QFrame { border: 1px solid #dee2e6; border-radius: 8px; padding: 12px; background: #fff; }")
        grid = QGridLayout(grid_frame)

        self.genre_in = QComboBox()
        self.genre_in.addItems(["Fiction", "Non-Fiction", "Fantasy", "Sci-Fi", "Mystery", "Horror", "History", "Biography", "Uncategorized"])
        self.status_in = QComboBox()
        self.status_in.addItems(["Read", "Currently Reading", "Want to Read", "Did Not Finish"])
        self.rating_in = QSpinBox(); self.rating_in.setRange(0, 5)
        self.pages_in = QLineEdit()
        self.year_in = QLineEdit()
        self.avg_rating_in = QLineEdit()
        
        # Интелигентно падащо меню за поредици
        self.series_in = QComboBox()
        self.series_in.setEditable(True)
        self.load_existing_series()
        
        self.series_num_in = QSpinBox(); self.series_num_in.setRange(0, 999)
        self.date_in = QDateEdit(); self.date_in.setCalendarPopup(True)

        grid.addWidget(QLabel("<b>Жанр:</b>"), 0, 0); grid.addWidget(self.genre_in, 0, 1)
        grid.addWidget(QLabel("<b>Година:</b>"), 0, 2); grid.addWidget(self.year_in, 0, 3)
        grid.addWidget(QLabel("<b>Статус:</b>"), 1, 0); grid.addWidget(self.status_in, 1, 1)
        grid.addWidget(QLabel("<b>Общ рейтинг:</b>"), 1, 2); grid.addWidget(self.avg_rating_in, 1, 3)
        grid.addWidget(QLabel("<b>Моят рейтинг:</b>"), 2, 0); grid.addWidget(self.rating_in, 2, 1)
        grid.addWidget(QLabel("<b>Поредица:</b>"), 2, 2); grid.addWidget(self.series_in, 2, 3)
        grid.addWidget(QLabel("<b>Страници:</b>"), 3, 0); grid.addWidget(self.pages_in, 3, 1)
        grid.addWidget(QLabel("<b>№ в поредица:</b>"), 3, 2); grid.addWidget(self.series_num_in, 3, 3)
        grid.addWidget(QLabel("<b>Завършена на:</b>"), 4, 0); grid.addWidget(self.date_in, 4, 1)

        content_layout.addWidget(grid_frame)

        # --- 4. ОПИСАНИЕ ---
        content_layout.addWidget(QLabel("<b>Анотация:</b>"))
        self.desc_in = QTextEdit()
        self.desc_in.setMinimumHeight(150)
        content_layout.addWidget(self.desc_in)

        scroll.setWidget(content_widget)
        outer_layout.addWidget(scroll)

        # --- 5. БУТОНИ ---
        btns = QHBoxLayout()
        save_btn = QPushButton("💾 ЗАПАЗИ")
        save_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 12px;")
        save_btn.clicked.connect(self.save_data)
        cancel_btn = QPushButton("Отказ")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(save_btn); btns.addWidget(cancel_btn)
        outer_layout.addLayout(btns)

        # Сигнали
        self.status_in.currentTextChanged.connect(self.toggle_date_field)
        self.browse_btn.clicked.connect(self.browse_local_image)
        self.web_cover_btn.clicked.connect(self.search_covers_online)
        self.clear_btn.clicked.connect(self.clear_current_cover)
        self.crawl_btn.clicked.connect(self.run_goodreads_crawl)

    def load_existing_series(self):
        """Зарежда всички уникални поредици от базата за улеснение."""
        try:
            df = database.fetch_all_books()
            if not df.empty and 'series_info' in df.columns:
                series_list = sorted(df['series_info'].unique().tolist())
                self.series_in.addItems([str(s) for s in series_list if s and str(s) != 'nan'])
        except: pass

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
        self.series_in.setEditText(str(d.get('series_info', '')))
        self.desc_in.setPlainText(str(d.get('description', '')))
        
        try:
            val = d.get('series_number')
            self.series_num_in.setValue(int(float(val)) if val not in [None, "", "nan"] else 0)
        except: self.series_num_in.setValue(0)

        date_str = str(d.get('date_finished', ''))
        if date_str and len(date_str) > 5:
            # Поддържаме и ISO и Mixed формат
            self.date_in.setDate(QDate.fromString(date_str[:10], "yyyy-MM-dd"))
        else: 
            self.date_in.setDate(QDate.currentDate())
        
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
                    with open(dest, "wb") as f: f.write(res.content)
                    self.cover_path_hidden = filename
                    self.update_cover_preview(dest)
                except Exception as e: QMessageBox.warning(self, "Грешка", str(e))

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

    def update_cover_preview(self, path):
        if not path: return
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
        # ВАЛИДАЦИЯ
        if not self.title_in.text().strip() or not self.author_in.text().strip():
            QMessageBox.warning(self, "Внимание", "Заглавието и авторът са задължителни!")
            return

        try:
            filename = os.path.basename(self.cover_path_hidden)
            
            # Синхронизация на корица
            if filename and filename != "default_cover.png":
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                database.upload_cover_to_supabase(filename)
                QApplication.restoreOverrideCursor()

            date_str = self.date_in.date().toString("yyyy-MM-dd") if self.status_in.currentText() == "Read" else ""

            # Подготовка на 16-те полета
            data = (
                str(self.title_in.text()).strip(),
                str(self.author_in.text()).strip(),
                int(self.rating_in.value()),
                str(self.status_in.currentText()),
                date_str,
                str(self.isbn_in.text()).strip(),
                str(self.desc_in.toPlainText()[:100]).replace("\n", " "),
                filename,
                str(self.series_in.currentText()).strip(),
                str(self.desc_in.toPlainText()),
                str(self.isbn_in.text()).strip(),
                str(self.pages_in.text()).strip(),
                str(self.avg_rating_in.text()).strip(),
                str(self.year_in.text()).strip(),
                str(self.genre_in.currentText()),
                str(self.series_num_in.value())
            )
            
            if self.book_id:
                if database.update_book_in_db(self.book_id, data): self.accept()
                else: raise Exception("Грешка при обновяване.")
            else:
                if database.add_new_book(data): self.accept()
                else: raise Exception("Грешка при добавяне.")
                    
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Грешка", str(e))

    def toggle_date_field(self, status):
        self.date_in.setEnabled(status == "Read")

    def run_goodreads_crawl(self):
        from logic.goodreads_scraper import scrape_goodreads
        from PyQt6.QtWidgets import QApplication, QMessageBox

        # Избираме заявка: ISBN има приоритет, ако липсва - заглавие
        query = self.isbn_in.text().strip() if self.isbn_in.text().strip() else self.title_in.text().strip()
        
        if not query: 
            QMessageBox.warning(self, "Внимание", "Моля, въведете заглавие или ISBN за търсене.")
            return

        # Визуална обратна връзка
        self.crawl_btn.setText("⏳ Проучване...")
        self.crawl_btn.setEnabled(False) # Деактивираме бутона, за да няма повторни заявки
        QApplication.processEvents()

        try:
            info = scrape_goodreads(query)
            
            if info:
                self.title_in.setText(info.get('title', ''))
                self.author_in.setText(info.get('author', ''))
                self.desc_in.setPlainText(info.get('description', ''))
                self.pages_in.setText(str(info.get('pages', '')))
                self.year_in.setText(str(info.get('year', '')))
                self.series_in.setEditText(info.get('series', ''))

                # --- ФИКС ЗА ГРЕШКАТА С ДРОБНИ ЧИСЛА (2.5, 1.5 и т.н.) ---
                raw_series_num = info.get('series_num', '0')
                try:
                    # Първо превръщаме в float (за да разбере точките), после в int
                    # Ако SpinBox-ът ти е цяло число, ще вземе '2' от '2.5'
                    clean_series_num = int(float(str(raw_series_num)))
                    self.series_num_in.setValue(clean_series_num)
                except (ValueError, TypeError):
                    self.series_num_in.setValue(0)

                self.avg_rating_in.setText(str(info.get('avg_rating', '')))
                QMessageBox.information(self, "Готово", "Данните са извлечени успешно!")
            else:
                QMessageBox.warning(self, "Няма резултати", "Goodreads не върна информация за тази книга.")

        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Възникна неочаквана грешка при пълзенето:\n{e}")

        finally:
            # Винаги връщаме бутона в първоначално състояние
            self.crawl_btn.setText("🚀 Deep Crawl (Goodreads)")
            self.crawl_btn.setEnabled(True)



   
