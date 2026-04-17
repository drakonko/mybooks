import os
import time
import shutil
import requests
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QLabel, 
                             QMessageBox, QApplication, QFrame)
import database

COVERS_DIR = "covers"

class BulkRepairDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Library Maintenance")
        self.resize(450, 300)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Section 1: Reset
        reset_frame = QFrame()
        reset_frame.setStyleSheet("background: #fff5f5; border: 1px solid #feb2b2; border-radius: 8px;")
        reset_lay = QVBoxLayout(reset_frame)
        reset_lay.addWidget(QLabel("<b>Dangerous Area: Reset Covers</b>"))
        
        self.btn_clear = QPushButton("🗑️ Delete All Local Covers & Reset DB")
        self.btn_clear.setStyleSheet("background-color: #e53e3e; color: white; font-weight: bold; padding: 10px;")
        self.btn_clear.clicked.connect(self.clear_all_covers)
        reset_lay.addWidget(self.btn_clear)
        layout.addWidget(reset_frame)

        layout.addSpacing(20)

        # Section 2: Repair
        repair_frame = QFrame()
        repair_frame.setStyleSheet("background: #f0fff4; border: 1px solid #9ae6b4; border-radius: 8px;")
        repair_lay = QVBoxLayout(repair_frame)
        repair_lay.addWidget(QLabel("<b>Repair Area: High-Res Download</b>"))
        
        self.btn_repair = QPushButton("🚀 Run High-Res Repair (Google Books)")
        self.btn_repair.setStyleSheet("background-color: #38a169; color: white; font-weight: bold; padding: 10px;")
        self.btn_repair.clicked.connect(self.run_repair)
        repair_lay.addWidget(self.btn_repair)
        layout.addWidget(repair_frame)

    def clear_all_covers(self):
        """Wipes the physical folder and clears the DB paths."""
        confirm = QMessageBox.question(
            self, "Confirm Full Reset", 
            "This will delete ALL images in your covers folder and reset all book cover paths in the database. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            # 1. Clear Folder
            if os.path.exists(COVERS_DIR):
                shutil.rmtree(COVERS_DIR)
            os.makedirs(COVERS_DIR)
            
            # 2. Clear Database
            if database.clear_all_cover_paths():
                QMessageBox.information(self, "Reset Complete", "All covers deleted. You can now run the High-Res Repair.")
                self.parent_window.load_data_from_db()
            else:
                QMessageBox.warning(self, "Database Error", "Failed to clear database paths.")

    def run_repair(self):
        """Your existing Google Books high-res logic."""
        df = self.parent_window.all_books_df
        to_fix = df[(df['cover_path'] == "") | (df['description'] == "") | (df['description'].isna())]
        
        if to_fix.empty:
            QMessageBox.information(self, "Library Clean", "No books found needing repair.")
            return

        count = 0
        success_count = 0
        
        for _, book in to_fix.iterrows():
            count += 1
            if hasattr(self.parent_window, 'status_label'):
                self.parent_window.status_label.setText(f"🔄 High-Res Repair: {count}/{len(to_fix)}...")
            QApplication.processEvents()
            
            try:
                search_query = f"intitle:{book['title']}+inauthor:{book['author']}"
                url = f"https://www.googleapis.com/books/v1/volumes?q={search_query}&maxResults=1"
                res = requests.get(url, timeout=10).json()

                if "items" in res:
                    info = res["items"][0]["volumeInfo"]
                    full_desc = info.get("description", "No description available.")
                    image_links = info.get("imageLinks", {})
                    
                    img_url = (image_links.get("extraLarge") or image_links.get("large") or 
                               image_links.get("medium") or image_links.get("thumbnail"))

                    cover_path = book['cover_path']
                    if img_url:
                        img_url = img_url.replace("http://", "https://")
                        if "zoom=1" in img_url: img_url = img_url.replace("zoom=1", "zoom=2")
                        
                        img_data = requests.get(img_url, timeout=10).content
                        filename = f"book_{book['id']}.jpg"
                        save_path = os.path.join(COVERS_DIR, filename)
                        with open(save_path, 'wb') as f: f.write(img_data)
                        cover_path = filename # Store relative path

                    database.update_book_in_db(book['id'], (
                        book['title'], book['author'], book['rating'], book['status'], 
                        book['date_finished'], book['isbn13'], full_desc[:150], 
                        cover_path, book['series_info'], full_desc, book['isbn'], 
                        book['number_of_pages'], book['average_rating'], 
                        book['year_published'], book['genre']
                    ))
                    success_count += 1
                time.sleep(0.4)
            except Exception as e:
                print(f"Error: {e}")

        self.parent_window.load_data_from_db()
        QMessageBox.information(self, "Success", f"Repaired {success_count} books.")

def run_bulk_update_logic(parent):
    """Entry point from main.py"""
    dialog = BulkRepairDialog(parent)
    dialog.exec()
