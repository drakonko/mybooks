import logging
import database
import pandas as pd
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, 
                             QHeaderView, QMessageBox, QFrame)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt

class AuthorBibliographyDialog(QDialog):
    def __init__(self, author_name, parent_window):
        super().__init__(parent_window)
        self.author_name = author_name
        self.parent_window = parent_window
        self.setWindowTitle(f"Bibliography: {author_name}")
        self.resize(850, 650)
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        header = QFrame()
        header.setStyleSheet("background-color: #f8f9fa; border-bottom: 1px solid #dee2e6;")
        h_layout = QHBoxLayout(header)
        h_layout.addWidget(QLabel(f"<h2>{self.author_name}</h2>"))
        self.stats_lbl = QLabel("Syncing...")
        h_layout.addStretch(); h_layout.addWidget(self.stats_lbl)
        layout.addWidget(header)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Title / Series", "Order", "Release", "Status"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tree)

        btns = QHBoxLayout()
        self.btn_fetch = QPushButton("🌐 Fetch Bibliography")
        self.btn_fetch.clicked.connect(self.fetch_external_data)
        self.btn_add = QPushButton("➕ Add to Library")
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self.add_to_library)
        self.tree.itemSelectionChanged.connect(lambda: self.btn_add.setEnabled(
            self.tree.currentItem() is not None and self.tree.currentItem().parent() is not None and "Missing" in self.tree.currentItem().text(3)))
        
        btns.addWidget(self.btn_fetch); btns.addWidget(self.btn_add)
        btns.addStretch(); btns.addWidget(QPushButton("Close", clicked=self.accept))
        layout.addLayout(btns)

    def refresh_data(self):
        self.tree.clear()
        owned = []
        if hasattr(self.parent_window, 'all_books_df'):
            df = self.parent_window.all_books_df
            owned = df[df['author'] == self.author_name]['title'].str.lower().str.strip().tolist()

        bib_df = database.fetch_author_bibliography(self.author_name)
        if bib_df.empty: return

        groups = bib_df.groupby('series_name')
        count = 0
        for s_name, group in groups:
            root = QTreeWidgetItem(self.tree, [s_name or "Standalone", "", "", ""])
            root.setBackground(0, QColor("#f1f2f6")); root.setExpanded(True)
            for _, row in group.iterrows():
                title = str(row['book_title'])
                has = title.lower().strip() in owned
                if has: count += 1
                item = QTreeWidgetItem(root, [title, str(row['series_order']), str(row['release_year']), "✅ Owned" if has else "➕ Missing"])
                item.setForeground(3, QColor("#27ae60" if has else "#e74c3c"))
        self.stats_lbl.setText(f"Owned: {count} / {len(bib_df)}")

    def fetch_external_data(self):
        from logic.scraper_bn import fetch_bibliography_from_bn
        conn = database.get_db_connection()
        conn.execute("DELETE FROM author_works WHERE author_name = ?", (self.author_name,))
        conn.commit(); conn.close()
        
        results = fetch_bibliography_from_bn(self.author_name)
        if results:
            for r in results: database.save_author_work(r)
            self.refresh_data()
        else: QMessageBox.warning(self, "Error", "No books found.")

    def add_to_library(self):
        item = self.tree.currentItem()
        title = item.text(0)
        data = (title, self.author_name, 0, 'Want to Read', '', '', '', 'default_cover.png', item.parent().text(0), '', '', '', '0', '0.0', item.text(2), '')
        if database.add_new_book(data):
            self.parent_window.load_data_from_db()
            self.refresh_data()
