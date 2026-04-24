import os
import sys
import requests
import urllib.parse
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QListWidget, QListWidgetItem, 
                             QMessageBox, QFrame, QComboBox, QWidget)
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtCore import Qt, QUrl

import database

# --- ЛОГИКА ЗА ПЪТИЩАТА ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

COVERS_DIR = os.path.join(BASE_DIR, "covers")
# Линк към твоя Supabase Storage за преглед на корици, които не са на диска ти
SUPABASE_IMG_URL = "https://pvajcaorfmgmdptrtdxh.supabase.co/storage/v1/object/public/covers/"

class ViewBookDialog(QDialog):
    def __init__(self, book_data, parent=None):
        super().__init__(parent)
        # Превръщаме в речник, ако данните идват като ред от DataFrame
        self.book_data = book_data.to_dict() if hasattr(book_data, 'to_dict') else book_data
        self.setWindowTitle(f"Детайли за: {self.book_data.get('title')}")
        self.resize(850, 650)
        
        layout = QHBoxLayout(self)
        
        # --- ЛЯВ ПАНЕЛ: Корица и Бързи действия ---
        left_panel = QVBoxLayout()
        
        self.cover_lbl = QLabel()
        self.cover_lbl.setFixedSize(240, 360)
        self.cover_lbl.setStyleSheet("border: 1px solid #dcdde1; background: #f5f6fa; border-radius: 10px;")
        self.cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.stars_lbl = QLabel()
        self.stars_lbl.setStyleSheet("font-size: 24px; color: #f1c40f; margin-top: 10px;")
        self.stars_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.tech_details_lbl = QLabel()
        self.tech_details_lbl.setStyleSheet("font-size: 13px; color: #7f8c8d; margin-top: 5px;")
        self.tech_details_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_kindle_cover = QPushButton("📺 Корица към Kindle")
        self.btn_kindle_cover.setStyleSheet("""
            background-color: #8e44ad; color: white; padding: 10px; 
            font-weight: bold; border-radius: 6px; margin-top: 10px;
        """)
        self.btn_kindle_cover.clicked.connect(self.sync_to_screensaver)

        status_label = QLabel("Бърза промяна на статус:")
        status_label.setStyleSheet("font-size: 11px; color: #7f8c8d; margin-top: 15px; font-weight: bold;")
        
        status_row = QHBoxLayout()
        self.status_dropdown = QComboBox()
        self.status_dropdown.addItems(["Want to Read", "Currently Reading", "Read", "Did Not Finish"])
        
        current_status = str(self.book_data.get('status', 'Want to Read'))
        idx = self.status_dropdown.findText(current_status)
        if idx >= 0: self.status_dropdown.setCurrentIndex(idx)

        self.btn_save_status = QPushButton("Запази")
        self.btn_save_status.setFixedWidth(70)
        self.btn_save_status.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 5px;")
        self.btn_save_status.clicked.connect(self.update_status_db)

        status_row.addWidget(self.status_dropdown)
        status_row.addWidget(self.btn_save_status)

        self.btn_goodreads = QPushButton("🌐 Виж в Goodreads")
        self.btn_goodreads.setStyleSheet("""
            background-color: #f4f1ea; color: #382110; border: 1px solid #d6d0c4; 
            padding: 10px; font-weight: bold; border-radius: 6px; margin-top: 10px;
        """)
        self.btn_goodreads.clicked.connect(self.open_goodreads)
        
        left_panel.addWidget(self.cover_lbl)
        left_panel.addWidget(self.stars_lbl)
        left_panel.addWidget(self.tech_details_lbl)
        left_panel.addWidget(self.btn_kindle_cover)
        left_panel.addWidget(status_label)
        left_panel.addLayout(status_row)
        left_panel.addWidget(self.btn_goodreads)
        left_panel.addStretch()
        
        layout.addLayout(left_panel)
        
        # --- ДЕСЕН ПАНЕЛ: Текст и Информация ---
        info_layout = QVBoxLayout()
        
        self.title_lbl = QLabel()
        self.title_lbl.setStyleSheet("font-size: 26px; font-weight: bold; color: #2c3e50;")
        self.title_lbl.setWordWrap(True)
        
        author_row = QHBoxLayout()
        self.author_lbl = QLabel()
        self.author_lbl.setStyleSheet("font-size: 18px; color: #34495e;")
        self.author_lbl.linkActivated.connect(self.handle_link_click)

        self.btn_biblio = QPushButton("📚 Библио")
        self.btn_biblio.setFixedWidth(100)
        self.btn_biblio.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px; border-radius: 4px;")
        self.btn_biblio.clicked.connect(lambda: self.handle_link_click(f"author:{self.book_data.get('author')}"))

        author_row.addWidget(self.author_lbl)
        author_row.addWidget(self.btn_biblio)
        author_row.addStretch()

        self.genre_lbl = QLabel()
        self.status_lbl = QLabel()
        self.series_lbl = QLabel()
        self.series_lbl.linkActivated.connect(self.handle_link_click)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #dcdde1; margin: 10px 0;")
        
        self.desc_box = QTextEdit()
        self.desc_box.setReadOnly(True)
        self.desc_box.setStyleSheet("background: transparent; border: none; font-size: 15px; color: #2f3640; line-height: 1.4;")
        
        button_layout = QHBoxLayout()
        self.edit_btn = QPushButton("✏️ Редактирай")
        self.edit_btn.setMinimumHeight(45)
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(self.handle_edit)

        self.delete_btn = QPushButton("🗑️ Изтрий")
        self.delete_btn.setMinimumHeight(45)
        self.delete_btn.setStyleSheet("color: white; background-color: #e74c3c; font-weight: bold;")
        self.delete_btn.clicked.connect(self.handle_delete)

        self.close_btn = QPushButton("Затвори")
        self.close_btn.setMinimumHeight(45)
        self.close_btn.setStyleSheet("background-color: #bdc3c7; font-weight: bold;")
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.edit_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.close_btn)
        
        info_layout.addWidget(self.title_lbl)
        info_layout.addLayout(author_row)
        info_layout.addWidget(self.genre_lbl)
        info_layout.addWidget(self.status_lbl)
        info_layout.addWidget(self.series_lbl) 
        info_layout.addWidget(sep)
        info_layout.addWidget(self.desc_box)
        info_layout.addLayout(button_layout)
        
        layout.addLayout(info_layout, stretch=1)
        self.refresh_ui()

    def update_status_db(self):
        """Бързо обновяване само на статуса в Supabase."""
        new_status = self.status_dropdown.currentText()
        book_id = self.book_data.get('id')
        try:
            database.update_book_status_only(book_id, new_status)
            self.book_data['status'] = new_status
            self.refresh_ui()
            
            # Опресняваме таблицата в главния прозорец
            if self.parent() and hasattr(self.parent(), 'load_data_from_db'):
                self.parent().load_data_from_db(False)
            
            self.btn_save_status.setText("✓")
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Неуспешно обновяване: {e}")

    def refresh_ui(self):
        d = self.book_data
        
        # --- КОРУЦИ: Локално -> Облак ---
        filename = os.path.basename(str(d.get('cover_path', '')))
        local_path = os.path.join(COVERS_DIR, filename)
        
        if os.path.exists(local_path):
            self.cover_lbl.setPixmap(QPixmap(local_path).scaled(240, 360, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            # Ако файлът го няма локално, опитваме да го заредим директно от Supabase URL
            try:
                img_url = SUPABASE_IMG_URL + urllib.parse.quote(filename)
                res = requests.get(img_url, timeout=3)
                if res.status_code == 200:
                    pix = QPixmap()
                    pix.loadFromData(res.content)
                    self.cover_lbl.setPixmap(pix.scaled(240, 360, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else: self.cover_lbl.setText("Корицата се качва...")
            except: self.cover_lbl.setText("Проблем с мрежата")

        r = int(d.get('rating', 0) or 0)
        self.stars_lbl.setText("★" * r + "☆" * (5 - r))
        
        self.tech_details_lbl.setText(f"📄 {d.get('number_of_pages', '???')} стр.  •  📅 {d.get('year_published', 'N/A')}")
        self.title_lbl.setText(str(d.get('title', 'Unknown')))
        self.author_lbl.setText(f"<b>Автор:</b> <a href='author:{d.get('author')}' style='color: #3498db; text-decoration:none;'>{d.get('author')}</a>")
        self.genre_lbl.setText(f"<b>Жанр:</b> {d.get('genre', 'Uncategorized')}")
        
        status = str(d.get('status', 'Want to Read'))
        color = "#27ae60" if status == "Read" else "#f39c12" if status == "Currently Reading" else "#2980b9"
        self.status_lbl.setText(f"<b>Статус:</b> {status}")
        self.status_lbl.setStyleSheet(f"font-size: 16px; color: {color}; font-weight: bold;")

        s = d.get('series_info', '')
        if s and str(s).lower() not in ["none", "", "nan", "0"]:
            self.series_lbl.setText(f"🔗 Поредица: <a href='series:{s}' style='color: #8e44ad;'>{s}</a> #{d.get('series_number', '?')}")
            self.series_lbl.show()
        else: self.series_lbl.hide()
        
        self.desc_box.setText(str(d.get('description', 'Няма описание.')))

    def sync_to_screensaver(self):
        try:
            from logic.kindle_manager import copy_cover_to_kindle
            filename = os.path.basename(self.book_data.get('cover_path', ''))
            path = os.path.join(COVERS_DIR, filename)
            success, msg = copy_cover_to_kindle(path, self.book_data['title'])
            QMessageBox.information(self, "Kindle", msg)
        except Exception as e:
            QMessageBox.warning(self, "Грешка", f"Синхронът се провали: {e}")

    def open_goodreads(self):
        url = f"https://www.goodreads.com/search?q={urllib.parse.quote(str(self.book_data.get('title')) + ' ' + str(self.book_data.get('author')))}"
        QDesktopServices.openUrl(QUrl(url))

    def handle_link_click(self, link):
        prefix, value = link.split(":", 1)
        if prefix == "author":
            from logic.author_manager import AuthorBibliographyDialog
            dlg = AuthorBibliographyDialog(value, self.parent())
            dlg.exec()
        else:
            dlg = GenericListDialog(prefix, value, self)
            dlg.exec()

    def handle_edit(self):
        from dialog_edit import EditBookDialog
        if EditBookDialog(self.book_data, self).exec(): 
            self.accept()

    def handle_delete(self):
        reply = QMessageBox.question(self, "Изтриване", f"Сигурен ли си, че искаш да премахнеш '{self.book_data.get('title')}'?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if database.delete_book(self.book_data.get('id')): 
                self.accept()

class GenericListDialog(QDialog):
    def __init__(self, filter_type, filter_value, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Резултати за: {filter_value}")
        self.resize(500, 450)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        
        # Ползваме данните от паметта на главния прозорец
        all_books = database.fetch_all_books()
        col = "series_info" if filter_type == "series" else "author"
        
        matches = all_books[all_books[col].astype(str).str.lower() == str(filter_value).lower()]
        
        for _, book in matches.iterrows():
            item = QListWidgetItem(f"📖 {book['title']} ({book['status']})")
            item.setData(Qt.ItemDataRole.UserRole, book.to_dict())
            self.list_widget.addItem(item)
            
        self.list_widget.itemDoubleClicked.connect(self.open_book)
        layout.addWidget(self.list_widget)
        
        btn = QPushButton("Затвори", clicked=self.accept)
        layout.addWidget(btn)

    def open_book(self, item):
        book_data = item.data(Qt.ItemDataRole.UserRole)
        self.close()
        ViewBookDialog(book_data, self.parent()).exec()
