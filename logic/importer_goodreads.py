import pandas as pd
from PyQt6.QtWidgets import QFileDialog, QMessageBox
import database 

def handle_goodreads_import(parent):
    file_path, _ = QFileDialog.getOpenFileName(parent, "Open Goodreads Export", "", "CSV Files (*.csv)")
    if not file_path: return
    
    try:
        # Четем всичко като текст, за да не загубим ISBN-ите
        df = pd.read_csv(file_path, dtype=str)
        imported_data = []
        
        for _, row in df.iterrows():
            title = str(row.get('Title', 'Unknown')).strip()
            author = str(row.get('Author', 'Unknown')).strip()
            
            # Логика за статус
            shelf = str(row.get('Exclusive Shelf', '')).lower()
            status = 'Read' if shelf == 'read' else 'Currently Reading' if shelf == 'currently-reading' else 'Want to Read'
            
            # Почистване на ISBN13 (Goodreads добавя '="...' в CSV-то)
            isbn13 = str(row.get('ISBN13', '')).replace('=', '').replace('"', '').split('.')[0]
            if 'E+' in isbn13 or isbn13 == 'nan': isbn13 = ""
            
            # Почистване на ISBN10
            isbn10 = str(row.get('ISBN', '')).replace('=', '').replace('"', '').split('.')[0]
            if 'E+' in isbn10 or isbn10 == 'nan': isbn10 = ""
            
            pages = str(row.get('Number of Pages', '0')).split('.')[0]
            year = str(row.get('Year Published', '')).split('.')[0]
            
            # Рейтинг (0-5)
            try:
                rating = int(float(row.get('My Rating', 0)))
            except:
                rating = 0

            # --- ВАЖНО: Трябва да са точно 16 полета за Supabase ---
            # 1.title, 2.author, 3.rating, 4.status, 5.date_finished, 6.isbn, 
            # 7.desc_short, 8.cover_path, 9.series_info, 10.description, 
            # 11.isbn13, 12.pages, 13.avg_rating, 14.year, 15.genre, 16.series_number
            data = (
                title, 
                author, 
                rating, 
                status, 
                "",            # date_finished
                isbn10,        # isbn (10)
                "",            # description_short
                "default_cover.png", 
                "",            # series_info
                "",            # description
                isbn13,        # isbn13
                pages, 
                "0.0",         # average_rating
                year, 
                'Uncategorized',
                '0'            # series_number (Новото 16-то поле)
            )
            imported_data.append(data)
        
        if not imported_data:
            QMessageBox.warning(parent, "Empty File", "No valid books found in the CSV.")
            return

        # Използваме новата функция за масово вмъкване
        success, count = database.bulk_import_books(imported_data)
        
        if success:
            QMessageBox.information(parent, "Done", f"Successfully imported {count} books from Goodreads!")
            parent.load_data_from_db()
            
    except Exception as e:
        QMessageBox.critical(parent, "Import Error", f"Failed to process CSV: {str(e)}")
