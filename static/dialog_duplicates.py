import os
import logging
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QComboBox, QLabel, 
                             QHeaderView, QMessageBox, QAbstractItemView, QWidget)
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtCore import Qt

import database

class DuplicateManagerDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Мениджър на дубликати (Cloud)")
        self.resize(1000, 600)
        
        self.setup_ui()
        self.run_scan()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Горна лента с филтри ---
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Търси дубликати по:"))
        
        self.criteria_box = QComboBox()
        self.criteria_box.addItem("ISBN13", "isbn13")
        self.criteria_box.addItem("Заглавие + Автор", "title_author")
        self.criteria_box.addItem("Само заглавие", "title")
        
        self.criteria_box.currentIndexChanged.connect(self.run_scan)
        filter_layout.addWidget(self.criteria_box)
        
        filter_layout.addStretch()
        
        self.refresh_btn = QPushButton("🔄 Повторно сканиране")
        self.refresh_btn.clicked.connect(self.run_scan)
        filter_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(filter_layout)

        # --- Таблица с резултати ---
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Статус", "Заглавие", "Автор", "ISBN13", "Действия"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.table)
        
        self.status_info = QLabel("Намерени: 0 дубликата")
        self.status_info.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.status_info)

    def run_scan(self):
        criteria = self.criteria_box.currentData()
        # Тук викаме новата функция от database.py
        df = database.get_duplicate_books(criteria)
        self.display_results(df, criteria)

    def display_results(self, df, criteria):
        self.table.setRowCount(0)
        if df is None or df.empty:
            self.status_info.setText("✨ Няма открити дубликати по този критерий.")
            return

        self.status_info.setText(f"Открити са {len(df)} потенциално дублирани записа.")
        
        current_group_key = None
        use_alt_color = False
        color_white = QColor("#ffffff")
        color_grey = QColor("#f2f7fb")

        for i, row in df.iterrows():
            r_idx = self.table.rowCount()
            self.table.insertRow(r_idx)

            # Логика за групиране по цвят
            title = str(row.get('title', ''))
            author = str(row.get('author', ''))
            isbn = str(row.get('isbn13', ''))

            if criteria == "isbn13":
                match_val = isbn
            elif criteria == "title":
                match_val = title.lower()
            else:
                match_val = f"{title.lower()}{author.lower()}"
            
            if match_val != current_group_key:
                use_alt_color = not use_alt_color
                current_group_key = match_val

            bg_color = color_grey if use_alt_color else color_white

            # Попълване на клетките
            cells = [
                str(row.get('id', '')),
                str(row.get('status', '')),
                title,
                author,
                isbn
            ]

            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setBackground(QBrush(bg_color))
                self.table.setItem(r_idx, col, item)

            # --- Бутони за действие ---
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)
            btn_layout.setSpacing(5)
            
            view_btn = QPushButton("👁")
            view_btn.setToolTip("Виж детайли")
            view_btn.setFixedWidth(35)
            view_btn.clicked.connect(lambda ch, bid=row['id']: self.view_book(bid))
            
            del_btn = QPushButton("🗑")
            del_btn.setToolTip("Изтрий този дубликат")
            del_btn.setFixedWidth(35)
            del_btn.setStyleSheet("color: #e74c3c; font-weight: bold;")
            del_btn.clicked.connect(lambda ch, bid=row['id']: self.delete_book(bid))
            
            btn_layout.addWidget(view_btn)
            btn_layout.addWidget(del_btn)
            btn_layout.addStretch()
            
            self.table.setCellWidget(r_idx, 5, btn_widget)

    def view_book(self, bid):
        # Опитваме се да намерим книгата в основния списък на родителя
        try:
            book_data = self.parent_window.all_books_df[self.parent_window.all_books_df['id'] == bid].iloc[0].to_dict()
            from dialog_view import ViewBookDialog
            ViewBookDialog(book_data, self).exec()
        except:
            QMessageBox.warning(self, "Грешка", "Не можах да заредя детайлите на книгата.")

    def delete_book(self, bid):
        reply = QMessageBox.question(self, "Потвърждение", "Сигурен ли си, че искаш да изтриеш този дублиран запис?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if database.delete_book(bid):
                self.run_scan() # Опресняваме списъка с дубликати
                self.parent_window.load_data_from_db(False) # Опресняваме главния прозорец
