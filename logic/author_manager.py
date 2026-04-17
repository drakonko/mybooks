import logging
import database
import pandas as pd
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, 
                             QHeaderView, QMessageBox, QFrame, QTabWidget, QWidget, QListWidget, QListWidgetItem)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt

class AuthorBibliographyDialog(QDialog):
    def __init__(self, author_name, parent_window):
        super().__init__(parent_window)
        self.author_name = author_name
        self.parent_window = parent_window
        self.setWindowTitle(f"Author Profile: {author_name}")
        self.resize(850, 650)
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QFrame()
        header.setStyleSheet("background-color: #f8f9fa; border-bottom: 1px solid #dee2e6;")
        h_layout = QHBoxLayout(header)
        h_layout.addWidget(QLabel(f"<h2>{self.author_name}</h2>"))
        self.stats_lbl = QLabel("")
        h_layout.addStretch(); h_layout.addWidget(self.stats_lbl)
        layout.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        
        # TAB 1: OWNED BOOKS
        self.owned_list = QListWidget()
        self.tabs.addTab(self.owned_list, "📚 My Library")

        # TAB 2: FULL BIBLIOGRAPHY (The Tree View)
        bib_container = QWidget()
        bib_layout = QVBoxLayout(bib_container)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Title / Series", "Order", "Release", "Status"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        bib_layout.addWidget(self.tree)
        
        # Action Buttons for Bibliography Tab
        btns = QHBoxLayout()
        self.btn_fetch = QPushButton("🌐 Fetch Bibliography from Web")
        self.btn_fetch.clicked.connect(self.fetch_external_data)
        self.btn_add = QPushButton("➕ Add Missing to Library")
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self.add_to_library)
        
        btns.addWidget(self.btn_fetch); btns.addWidget(self.btn_add)
        bib_layout.addLayout(btns)
        
        self.tabs.addTab(bib_container, "📜 Full Bibliography")
        layout.addWidget(self.tabs)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(QPushButton("Close", clicked=self.accept))
        layout.addLayout(footer)

        self.tree.itemSelectionChanged.connect(self.toggle_add_button)

    def toggle_add_button(self):
        item = self.tree.currentItem()
        # Проверка дали елементът е книга (има родител серия) и дали е маркиран като Missing
        is_missing = item and item.parent() and "Missing" in item.text(3)
        self.btn_add.setEnabled(bool(is_missing))

    def refresh_data(self):
        self.owned_list.clear()
        self.tree.clear()
        
        # 1. Load Owned Books (от Supabase през Pandas)
        all_books = database.fetch_all_books()
        # Филтрираме в Pandas (case-insensitive за сигурност)
        owned_df = all_books[all_books['author'].str.lower() == self.author_name.lower()]
        owned_titles = [str(t).lower().strip() for t in owned_df['title'].tolist()]
        
        for _, row in owned_df.iterrows():
            item = QListWidgetItem(f"📖 {row['title']} [{row['status']}]")
            self.owned_list.addItem(item)

        # 2. Load Bibliography
        bib_df = database.fetch_author_bibliography(self.author_name)
        if bib_df.empty:
            self.stats_lbl.setText(f"Owned: {len(owned_df)} | Biblio: Not Sync'd")
            return

        # Групираме по серия
        groups = bib_df.groupby('series_name')
        bib_count = 0
        for s_name, group in groups:
            display_name = s_name if s_name and str(s_name).strip() != "" else "Standalone Novels"
            root = QTreeWidgetItem(self.tree, [display_name, "", "", ""])
            root.setBackground(0, QColor("#f1f2f6"))
            root.setExpanded(True)
            
            for _, row in group.iterrows():
                title = str(row['book_title'])
                is_owned = title.lower().strip() in owned_titles
                if is_owned: bib_count += 1
                
                status_text = "✅ Owned" if is_owned else "➕ Missing"
                item = QTreeWidgetItem(root, [title, str(row['series_order']), str(row['release_year']), status_text])
                item.setForeground(3, QColor("#27ae60" if is_owned else "#e74c3c"))
                
        self.stats_lbl.setText(f"Owned: {len(owned_df)} | Biblio Sync: {bib_count}/{len(bib_df)}")

    def fetch_external_data(self):
        from logic.scraper_bn import fetch_bibliography_from_bn
        
        self.btn_fetch.setText("⏳ Fetching...")
        self.btn_fetch.setEnabled(False)
        
        try:
            results = fetch_bibliography_from_bn(self.author_name)
            if results:
                # 1. Изчистваме старата библиография за този автор в Supabase
                conn = database.get_db_connection()
                try:
                    with conn.cursor() as cur:
                        # В Postgres ползваме %s и курсор
                        cur.execute("DELETE FROM author_works WHERE author_name = %s", (self.author_name,))
                    conn.commit()
                finally:
                    conn.close()
                
                # 2. Записваме новите данни
                for r in results:
                    database.save_author_work(r)
                
                self.refresh_data()
                QMessageBox.information(self, "Success", f"Retrieved {len(results)} works from Web.")
            else:
                QMessageBox.warning(self, "Error", "No books found online for this author.")
        except Exception as e:
            QMessageBox.critical(self, "Critical Error", f"Scraper Error: {e}")
        finally:
            self.btn_fetch.setText("🌐 Fetch Bibliography from Web")
            self.btn_fetch.setEnabled(True)

    def add_to_library(self):
        item = self.tree.currentItem()
        if not item: return
        
        title = item.text(0)
        # Взимаме името на серията от родителя в дървото
        parent_text = item.parent().text(0)
        series = parent_text if parent_text != "Standalone Novels" else ""
        
        # Подготвяме точно 16 параметъра според дефиницията в database.add_new_book
        # (title, author, rating, status, date_finished, isbn, description_short, cover_path, 
        #  series_info, description, isbn13, pages, avg_rating, year, genre, series_num)
        data = (
            title, 
            self.author_name, 
            0,                     # rating
            'Want to Read',        # status
            '',                    # date_finished
            '',                    # isbn
            '',                    # description_short
            'default_cover.png',   # cover_path
            series,                # series_info
            '',                    # description
            '',                    # isbn13
            '0',                   # number_of_pages
            '0.0',                 # average_rating
            item.text(2),          # year_published (Release column)
            'Uncategorized',       # genre
            item.text(1)           # series_number (Order column)
        )
        
        if database.add_new_book(data):
            if hasattr(self.parent_window, 'load_data_from_db'):
                self.parent_window.load_data_from_db(False)
            self.refresh_data()
            QMessageBox.information(self, "Added", f"'{title}' has been added to your Want to Read list.")
