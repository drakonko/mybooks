import requests
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QLabel, 
                             QPushButton, QHBoxLayout, QMessageBox, QApplication)

class AddBookSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавяне на нова книга")
        self.setFixedWidth(450)
        self.result_data = None
        
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Вариант 1: Търсене в Google Books</b>"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Въведи ISBN, заглавие или автор...")
        layout.addWidget(self.search_input)

        search_btn = QPushButton("🔍 Търси онлайн")
        search_btn.setStyleSheet("background-color: #3498db; color: white; padding: 10px; font-weight: bold;")
        search_btn.clicked.connect(self.search_google)
        layout.addWidget(search_btn)

        layout.addWidget(QLabel("<br><b>Вариант 2: Ръчно въвеждане</b>"))
        manual_btn = QPushButton("📝 Попълни данните ръчно")
        manual_btn.clicked.connect(self.open_manual)
        layout.addWidget(manual_btn)

    def search_google(self):
        query = self.search_input.text().strip()
        if not query: return
        
        self.setWindowTitle("⏳ Търсене...")
        QApplication.processEvents()

        try:
            # Премахваме тиретата, ако потребителят търси по ISBN
            clean_query = query.replace("-", "").replace(" ", "")
            if clean_query.isdigit() and len(clean_query) in [10, 13]:
                search_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_query}"
            else:
                search_url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=1"

            res = requests.get(search_url, timeout=10)
            data = res.json()
            
            if "items" in data:
                item = data["items"][0]["volumeInfo"]
                
                # Пълно мапване към всички 17 полета на Supabase таблицата
                self.result_data = {
                    'id': None, 
                    'title': item.get('title', 'Unknown Title'),
                    'author': ", ".join(item.get('authors', ['Unknown Author'])),
                    'rating': 0,
                    'status': 'Want to Read',
                    'date_finished': '',  # Ново: Задължително за Supabase
                    'isbn13': '', 
                    'description_short': item.get('description', '')[:100],
                    'cover_path': '',
                    'series_info': '',
                    'description': item.get('description', 'No description available.'),
                    'isbn': '',
                    'number_of_pages': str(item.get('pageCount', '0')),
                    'average_rating': str(item.get('averageRating', '')),
                    'year_published': item.get('publishedDate', '0000')[:4],
                    'genre': item.get('categories', ['Uncategorized'])[0],
                    'series_number': '' # Ново: Задължително за Supabase
                }
                
                # Извличане на ISBN
                for identifier in item.get('industryIdentifiers', []):
                    if identifier['type'] == 'ISBN_13':
                        self.result_data['isbn13'] = identifier['identifier']
                        self.result_data['isbn'] = identifier['identifier'] # За по-стари версии
                    elif identifier['type'] == 'ISBN_10' and not self.result_data['isbn13']:
                        self.result_data['isbn'] = identifier['identifier']

                self.accept()
            else:
                QMessageBox.warning(self, "Няма резултати", f"Не открихме '{query}'. Опитай с точен ISBN.")
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Търсенето пропадна: {e}")
        finally:
            self.setWindowTitle("Добавяне на нова книга")

    def open_manual(self):
        # Шаблон за ръчно въвеждане с всички нужни полета
        self.result_data = {
            'id': None,
            'title': '',
            'author': '',
            'rating': 0,
            'status': 'Want to Read',
            'date_finished': '',
            'isbn13': '',
            'description_short': '',
            'cover_path': '',
            'series_info': '',
            'description': '',
            'isbn': '',
            'number_of_pages': '',
            'average_rating': '',
            'year_published': '',
            'genre': 'Uncategorized',
            'series_number': ''
        }
        self.accept()
