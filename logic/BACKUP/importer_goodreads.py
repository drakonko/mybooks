import pandas as pd
from PyQt6.QtWidgets import QFileDialog, QMessageBox
import database # Ensure your database.py script is importable

def handle_goodreads_import(parent):
    file_path, _ = QFileDialog.getOpenFileName(parent, "Open Goodreads Export", "", "CSV Files (*.csv)")
    if not file_path: return
    
    try:
        df = pd.read_csv(file_path, dtype=str)
        imported_data = []
        for _, row in df.iterrows():
            title = str(row.get('Title', 'Unknown')).strip()
            author = str(row.get('Author', 'Unknown')).strip()
            status = 'Read' if row.get('Exclusive Shelf') == 'read' else 'Want to Read'
            
            isbn13 = str(row.get('ISBN13', '')).replace('=', '').replace('"', '').split('.')[0]
            if 'E+' in isbn13: isbn13 = ""
            
            pages = str(row.get('Number of Pages', '')).split('.')[0]
            year = str(row.get('Year Published', '')).split('.')[0]
            rating = int(float(row.get('My Rating', 0))) if pd.notnull(row.get('My Rating')) else 0

            # This tuple structure must match your database.bulk_import_books expectation
            data = (title, author, rating, status, "", isbn13, "", "", "", "", "", pages, "", year, 'Uncategorized')
            imported_data.append(data)
        
        success, counts = database.bulk_import_books(imported_data)
        if success:
            QMessageBox.information(parent, "Done", f"Added {counts[0]} books.")
            parent.load_data_from_db()
            
    except Exception as e:
        QMessageBox.critical(parent, "Import Error", f"Failed to process CSV: {str(e)}")