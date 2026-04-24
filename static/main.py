import logging
import traceback
import sys, os, pandas as pd
import math
import requests
import urllib.parse
import datetime
from dotenv import load_dotenv

from PyQt6.QtWidgets import (QMainWindow, QApplication, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHeaderView, 
                             QAbstractItemView, QComboBox, QFileDialog, QMessageBox,
                             QFrame, QButtonGroup, QScrollArea, QGridLayout, QProgressBar, 
                             QInputDialog, QDialog)
from PyQt6.QtGui import QPixmap, QBrush, QColor
from PyQt6.QtCore import Qt

# Вътрешни импорти
import database
from dialog_view import ViewBookDialog
from dialog_add import AddBookSearchDialog
from dialog_edit import EditBookDialog

# Логика и модули
from logic.stats_dashboard import show_stats_dashboard
from logic.importer_goodreads import handle_goodreads_import
from logic.bulk_operations import run_bulk_update_logic
from logic.kindle_manager import run_kindle_sync

load_dotenv()

# Настройки за облака
SUPABASE_IMG_URL = "https://pvajcaorfmgmdptrtdxh.supabase.co/storage/v1/object/public/covers/"

# Конфигурация на логването
logging.basicConfig(
    filename='debug_log.txt',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

COVERS_DIR = os.path.join(BASE_DIR, "covers")
if not os.path.exists(COVERS_DIR):
    os.makedirs(COVERS_DIR)

class ReadingDiary(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Моят личен читателски дневник 2026")
        self.resize(1350, 800)

        self.mgmt_status_lbl = None
        self.mgmt_progress_bar = None
        
        self.all_books_df = pd.DataFrame() 
        self.filtered_df = pd.DataFrame()
        
        self.current_page = 0
        self.page_size = 15
        
        # Инициализация на БД
        try:
            database.create_database()
            database.cleanup_unfinished_book_dates()
        except Exception as e:
            logging.error(f"Грешка при връзка с облака: {e}")

        self.init_ui()
        self.load_data_from_db()

    def init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Хедър
        header = QHBoxLayout()
        self.stat_lbl = QLabel("📚 Книги: 0")
        self.stat_lbl.setStyleSheet("font-weight: bold; font-size: 14px; background: #f0f2f5; padding: 10px 20px; border-radius: 8px;")
        
        # Цел за 2026
        self.goal_widget = QWidget()
        goal_layout = QHBoxLayout(self.goal_widget)
        goal_layout.setContentsMargins(15, 0, 0, 0)
        
        self.goal_label = QLabel("🎯 Цел 2026: 0/50")
        self.goal_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 13px;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.setMaximum(50) 
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #bdc3c7; border-radius: 4px; text-align: center; height: 18px; background: #ecf0f1; font-weight: bold; font-size: 10px; }
            QProgressBar::chunk { background-color: #27ae60; }
        """)
        
        goal_layout.addWidget(self.goal_label)
        goal_layout.addWidget(self.progress_bar)

        self.mgmt_btn = QPushButton("⚙️ Управление")
        self.mgmt_btn.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; padding: 10px 20px; border-radius: 5px;")
        self.mgmt_btn.clicked.connect(self.open_management_center)

        self.add_btn = QPushButton("➕ Нова книга")
        self.add_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 10px 20px; border-radius: 5px;")
        self.add_btn.clicked.connect(self.handle_add)
        
        header.addWidget(self.stat_lbl)
        header.addWidget(self.goal_widget)
        header.addStretch()
        header.addWidget(self.mgmt_btn)
        header.addWidget(self.add_btn)
        layout.addLayout(header)

        # Табове
        self.tab_frame = QFrame()
        self.tab_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border-bottom: 2px solid #dee2e6; } QPushButton { border: none; padding: 12px 20px; font-weight: bold; } QPushButton:checked { color: #3498db; border-bottom: 3px solid #3498db; }")
        tab_layout = QHBoxLayout(self.tab_frame)
        self.status_group = QButtonGroup(self)
        
        categories = [("Всички", "All"), ("Прочетени", "Read"), ("В момента", "Currently Reading"), ("Искам", "Want to Read")]
        for text, value in categories:
            btn = QPushButton(text); btn.setCheckable(True); btn.setProperty("filter_val", value)
            if value == "All": btn.setChecked(True)
            btn.clicked.connect(lambda: self.apply_filters(True))
            self.status_group.addButton(btn); tab_layout.addWidget(btn)
        tab_layout.addStretch(); layout.addWidget(self.tab_frame)

        # Филтри
        filter_layout = QHBoxLayout()
        self.search_bar = QLineEdit(); self.search_bar.setPlaceholderText("🔍 Търси по заглавие или автор...")
        self.search_bar.textChanged.connect(lambda: self.apply_filters(True))
        
        self.genre_filter = QComboBox()
        self.genre_filter.addItems(["Всички жанрове", "Fiction", "Non-Fiction", "Fantasy", "Sci-Fi", "Mystery", "Uncategorized"])
        self.genre_filter.currentTextChanged.connect(lambda: self.apply_filters(True))
        
        self.sort_box = QComboBox(); self.sort_box.addItems(["Сортирай: Заглавие", "Сортирай: Рейтинг"])
        self.sort_box.currentTextChanged.connect(lambda: self.apply_filters(True))
        
        filter_layout.addWidget(self.search_bar, 3); filter_layout.addWidget(self.genre_filter, 1); filter_layout.addWidget(self.sort_box, 1)
        layout.addLayout(filter_layout)

        # Съдържание
        main_content = QHBoxLayout()
        self.table = QTableWidget(0, 4); self.table.setHorizontalHeaderLabels(["#", "Заглавие", "Автор", "Жанр"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 45); self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.itemSelectionChanged.connect(self.update_sidebar); self.table.cellDoubleClicked.connect(self.open_details)
        main_content.addWidget(self.table, 3)

        # Страничен панел (Sidebar)
        self.sidebar_v = QVBoxLayout()
        self.side_cover = QLabel(); self.side_cover.setFixedSize(220, 330); self.side_cover.setStyleSheet("border: 1px solid #ddd; background: #fff; border-radius: 5px;")
        self.side_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.side_title = QLabel("Избери книга"); self.side_title.setWordWrap(True)
        self.side_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #2c3e50;")
        
        self.side_series = QLabel(""); self.side_series.setWordWrap(True)
        self.side_series.setStyleSheet("color: #8e44ad; font-style: italic; font-size: 13px;")
        
        self.side_desc = QLabel(""); self.side_desc.setWordWrap(True)
        self.side_desc.setStyleSheet("color: #7f8c8d; font-size: 13px;")
        
        self.view_btn = QPushButton("👁 Детайли"); self.view_btn.setEnabled(False); self.view_btn.clicked.connect(self.open_details)
        self.view_btn.setMinimumHeight(40)
        
        self.sidebar_v.addWidget(self.side_cover)
        self.sidebar_v.addWidget(self.side_title)
        self.sidebar_v.addWidget(self.side_series)
        self.sidebar_v.addWidget(self.side_desc)
        self.sidebar_v.addStretch()
        self.sidebar_v.addWidget(self.view_btn)
        
        main_content.addLayout(self.sidebar_v, 1)
        layout.addLayout(main_content)

        # Навигация
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("⬅️ Предишна"); self.prev_btn.clicked.connect(self.prev)
        self.next_btn = QPushButton("Следваща ➡️"); self.next_btn.clicked.connect(self.next)
        self.page_lbl = QLabel("Страница 1 от 1")
        nav.addStretch(); nav.addWidget(self.prev_btn); nav.addWidget(self.page_lbl); nav.addWidget(self.next_btn); nav.addStretch()
        layout.addLayout(nav)

    def load_data_from_db(self, reset=True):
        self.all_books_df = database.fetch_all_books()
        self.apply_filters(reset)

    def apply_filters(self, reset=True):
        query = self.search_bar.text().lower()
        active_status = self.status_group.checkedButton().property("filter_val")
        selected_genre = self.genre_filter.currentText()
        sort_mode = self.sort_box.currentText()
        
        df = self.all_books_df.copy()
        if active_status != "All": df = df[df['status'] == active_status]
        if selected_genre != "Всички жанрове": df = df[df['genre'] == selected_genre]
        if query: 
            df = df[df['title'].str.lower().str.contains(query, na=False, regex=False) | 
                    df['author'].str.lower().str.contains(query, na=False, regex=False)]
        
        if "Заглавие" in sort_mode: df = df.sort_values(by='title')
        elif "Рейтинг" in sort_mode: df = df.sort_values(by='rating', ascending=False)
        
        self.filtered_df = df
        if reset: self.current_page = 0
        self.display()

    def display(self):
        self.table.setRowCount(0)
        total_items = len(self.filtered_df)
        total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1
        
        if self.current_page >= total_pages: self.current_page = max(0, total_pages - 1)
        start = self.current_page * self.page_size
        page_data = self.filtered_df.iloc[start : start + self.page_size]
        
        for i, (idx, row) in enumerate(page_data.iterrows()):
            r = self.table.rowCount(); self.table.insertRow(r)
            idx_item = QTableWidgetItem(str(start + i + 1))
            idx_item.setData(Qt.ItemDataRole.UserRole, row['id'])
            self.table.setItem(r, 0, idx_item)
            self.table.setItem(r, 1, QTableWidgetItem(str(row['title'])))
            self.table.setItem(r, 2, QTableWidgetItem(str(row['author'])))
            self.table.setItem(r, 3, QTableWidgetItem(str(row['genre'])))
        
        self.page_lbl.setText(f"Страница <b>{self.current_page + 1}</b> от <b>{total_pages}</b>")
        self.stat_lbl.setText(f"📚 Книги: {total_items}")

        # Обновяване на прогреса за 2026
        try:
            read_count = database.get_2026_read_count()
            self.progress_bar.setValue(read_count)
            self.goal_label.setText(f"🎯 Цел 2026: {read_count}/{self.progress_bar.maximum()}")
        except: pass
        
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)

    def next(self): self.current_page += 1; self.display()
    def prev(self): self.current_page -= 1; self.display()

    def update_sidebar(self):
        row = self.table.currentRow()
        if row < 0: 
            self.view_btn.setEnabled(False); return
        
        bid = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        book = self.all_books_df[self.all_books_df['id'] == bid].iloc[0]
        
        self.side_title.setText(f"<b>{book['title']}</b>")
        
        # Поредица
        series = book.get('series_info', '')
        series_num = book.get('series_number', '')
        if series and str(series).lower() not in ["none", "nan", "", "0"]:
            num_text = f", Книга {series_num}" if series_num and str(series_num) != "0" else ""
            self.side_series.setText(f"🔗 {series}{num_text}")
            self.side_series.show()
        else: self.side_series.hide()

        # Описание
        desc = str(book.get('description', ''))
        self.side_desc.setText(desc[:140] + "..." if len(desc) > 140 else desc)
        
        # КОРИЦА (Cloud-Safe Logic)
        filename = os.path.basename(str(book.get('cover_path', '')))
        local_path = os.path.join(COVERS_DIR, filename)
        
        if os.path.exists(local_path):
            self.side_cover.setPixmap(QPixmap(local_path).scaled(220, 330, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            # Опит за зареждане директно от Supabase
            try:
                img_url = SUPABASE_IMG_URL + urllib.parse.quote(filename)
                res = requests.get(img_url, timeout=3)
                if res.status_code == 200:
                    pix = QPixmap(); pix.loadFromData(res.content)
                    self.side_cover.setPixmap(pix.scaled(220, 330, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else: self.side_cover.setText("Няма корица")
            except: self.side_cover.setText("Грешка при заред.")

        self.view_btn.setEnabled(True)

    def open_details(self):
        row = self.table.currentRow()
        if row >= 0:
            bid = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            book_data = self.all_books_df[self.all_books_df['id'] == bid].iloc[0].to_dict()
            if ViewBookDialog(book_data, self).exec(): self.load_data_from_db(False)

    def handle_add(self):
        search_dlg = AddBookSearchDialog(self)
        if search_dlg.exec():
            if EditBookDialog(search_dlg.result_data, self).exec(): self.load_data_from_db()

    def open_management_center(self):
        from dialog_management import ManagementCenterDialog
        if ManagementCenterDialog(self).exec(): self.load_data_from_db(False)

    def run_manual_backup_logic(self):
        """Експортира текущите данни в CSV файл (подходящо за облака)."""
        try:
            filename, _ = QFileDialog.getSaveFileName(self, "Запази архив", f"library_backup_{datetime.date.today()}.csv", "CSV Files (*.csv)")
            if filename:
                self.all_books_df.to_csv(filename, index=False, encoding='utf-8-sig')
                QMessageBox.information(self, "Успех", "Архивът е създаден успешно.")
        except Exception as e: QMessageBox.warning(self, "Грешка", str(e))

    def show_stats(self): show_stats_dashboard(self)
    def handle_import(self): handle_goodreads_import(self)
    def run_kindle_sync_logic(self): run_kindle_sync(self)
    def run_bulk_update(self): run_bulk_update_logic(self)

if __name__ == "__main__":
    from PyQt6.QtWidgets import QSplashScreen
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtCore import Qt, QTimer

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 1. СЪЗДАВАНЕ НА SPLASH SCREEN
    # Увери се, че файлът "start_image.png" е в основната папка
    pixmap = QPixmap("start_image.png") # Тук сложи името на твоята картинка
    
    if pixmap.isNull():
        # Ако картинката липсва, създаваме временен етикет, за да не гърми
        splash = QSplashScreen()
        splash.showMessage("Зареждане на дневника...", Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom, Qt.GlobalColor.white)
    else:
        # Мащабираме картинката, ако е твърде голяма (например 600px ширина)
        splash = QSplashScreen(pixmap.scaled(600, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    # Правим го винаги отгоре и го показваме
    splash.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
    splash.show()
    
    # Текст върху картинката (опционално)
    splash.showMessage("Свързване с облака на Supabase...", 
                       Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
                       Qt.GlobalColor.white)
    
    # Принуждаваме Windows да изчертае картинката веднага
    QApplication.processEvents()

    # 2. ИНИЦИАЛИЗАЦИЯ НА ПРИЛОЖЕНИЕТО
    # Докато splash е на екрана, Python изпълнява __init__ на ReadingDiary
    window = ReadingDiary()

    # 3. ПРЕХОД КЪМ ГЛАВНИЯ ПРОЗОРЕЦ
    # Задържаме splash-а за още половин секунда, за да не е твърде рязко
    QTimer.singleShot(1500, lambda: (splash.finish(window), window.show()))

    sys.exit(app.exec())
