import os
import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QFileDialog, QMessageBox, QListWidget, QProgressBar)
from PyQt6.QtCore import Qt

class KindleSyncDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Kindle Device Sync")
        self.resize(500, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.info_lbl = QLabel(
            "<b>Instructions:</b><br>"
            "1. Connect your Kindle to your computer via USB.<br>"
            "2. Locate the <b>'documents'</b> folder on the Kindle drive.<br>"
            "3. Select the <b>'My Clippings.txt'</b> file."
        )
        self.info_lbl.setWordWrap(True)
        layout.addWidget(self.info_lbl)

        self.btn_select = QPushButton("📂 Select My Clippings.txt")
        self.btn_select.setStyleSheet("padding: 10px; font-weight: bold;")
        self.btn_select.clicked.connect(self.parse_clippings)
        layout.addWidget(self.btn_select)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        layout.addWidget(QLabel("<b>Found Books in Clippings:</b>"))
        self.book_list = QListWidget()
        layout.addWidget(self.book_list)

        self.btn_import = QPushButton("Add Selected to Diary")
        self.btn_import.setEnabled(False)
        self.btn_import.setStyleSheet("background-color: #f39c12; color: white;")
        self.btn_import.clicked.connect(self.import_to_db)
        layout.addWidget(self.btn_import)

    def parse_clippings(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Kindle Clippings", "", "Text Files (My Clippings.txt)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()

            # Kindle clippings are separated by "=========="
            entries = content.split("==========")
            discovered_books = {} # Title -> Author

            for entry in entries:
                lines = [l.strip() for l in entry.strip().split('\n') if l.strip()]
                if len(lines) >= 2:
                    # Line 0 usually: Title (Author Name)
                    header = lines[0]
                    match = re.search(r'^(.*)\((.*)\)$', header)
                    if match:
                        title = match.group(1).strip()
                        author = match.group(2).strip()
                        discovered_books[title] = author
                    else:
                        discovered_books[header] = "Unknown Kindle Author"

            self.book_list.clear()
            for title, author in discovered_books.items():
                self.book_list.addItem(f"{title} — {author}")
            
            if discovered_books:
                self.btn_import.setEnabled(True)
                QMessageBox.information(self, "Scan Complete", f"Found {len(discovered_books)} unique books in your clippings.")
            else:
                QMessageBox.warning(self, "No Data", "No valid book entries found in that file.")

        except Exception as e:
            QMessageBox.critical(self, "Sync Error", f"Failed to read file: {e}")

    def import_to_db(self):
        """Passes the found books to the database bulk importer."""
        items = [self.book_list.item(i).text() for i in range(self.book_list.count())]
        if not items:
            return

        formatted_data = []
        for item in items:
            title, author = item.split(" — ")
            # (title, author, rating, status, date, isbn13, desc_s, cover, series, desc, isbn, pages, avg_rate, year, genre)
            book_tuple = (
                title, author, 0, 'Currently Reading', "", "", "", 
                "default_cover.png", "", "Imported via Kindle Sync", 
                "", "0", "0.0", "2025", "Kindle Import"
            )
            formatted_data.append(book_tuple)

        import database
        success, counts = database.bulk_import_books(formatted_data)
        
        if success:
            QMessageBox.information(self, "Success", f"Synced {counts[0]} new books! (Skipped {counts[1]} duplicates)")
            self.parent_window.load_data_from_db()
            self.accept()

def run_kindle_sync(parent):
    """Entry point called by main.py"""
    dialog = KindleSyncDialog(parent)
    dialog.exec()