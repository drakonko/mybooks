import logging
import traceback
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QGridLayout, 
                             QPushButton, QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt

class ManagementCenterDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        logging.info("ManagementCenterDialog: Starting __init__")
        
        try:
            self.parent_window = parent  # Основният прозорец ReadingDiary
            self.setWindowTitle("Център за управление на системата")
            self.setFixedSize(550, 520) 
            
            self.setup_ui()
            logging.info("ManagementCenterDialog: __init__ successful")
            
        except Exception as e:
            logging.error(f"ManagementCenterDialog: Failed to initialize: {e}")
            logging.error(traceback.format_exc())

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- ЗАГЛАВИЕ ---
        title = QLabel("🛠️ Инструменти и управление на библиотеката")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px; color: #2c3e50;")
        layout.addWidget(title)
        
        # --- ГРИД С БУТОНИ ---
        grid = QGridLayout()
        grid.setSpacing(15)
        
        self.btn_stats = QPushButton("📊 Статистика и\nанализи")
        self.btn_stats.clicked.connect(self.safe_stats)
        
        self.btn_repair = QPushButton("🚀 Масова поправка\nна корици")
        self.btn_repair.clicked.connect(self.safe_repair)
        
        self.btn_import = QPushButton("📥 Импорт от\nGoodreads (CSV)")
        self.btn_import.clicked.connect(self.safe_import)
        
        self.btn_kindle = QPushButton("🔥 Kindle\nСинхронизация")
        self.btn_kindle.clicked.connect(self.safe_kindle)
        
        self.btn_dupes = QPushButton("🔍 Търсене на\nдубликати")
        self.btn_dupes.clicked.connect(self.safe_dupes)
        
        self.btn_backup = QPushButton("💾 Ръчен архив\n(Backup)")
        self.btn_backup.clicked.connect(self.safe_backup)

        # Подредба в мрежата
        grid.addWidget(self.btn_stats, 0, 0)
        grid.addWidget(self.btn_repair, 0, 1)
        grid.addWidget(self.btn_import, 1, 0)
        grid.addWidget(self.btn_kindle, 1, 1)
        grid.addWidget(self.btn_dupes, 2, 0)
        grid.addWidget(self.btn_backup, 2, 1)

        # Стилизиране на бутоните
        for btn in [self.btn_stats, self.btn_repair, self.btn_import, 
                    self.btn_kindle, self.btn_dupes, self.btn_backup]:
            btn.setMinimumHeight(85)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    font-weight: bold; 
                    font-size: 13px; 
                    background-color: #fdfdfd; 
                    border: 1px solid #d1d1d1;
                    border-radius: 8px;
                    color: #2c3e50;
                }
                QPushButton:hover {
                    background-color: #f1f1f1;
                    border: 1px solid #3498db;
                    color: #3498db;
                }
                QPushButton:pressed {
                    background-color: #dcdde1;
                }
            """)
            
        layout.addLayout(grid)

        # --- СТАТУС И ПРОГРЕС ---
        layout.addSpacing(20)
        self.status_lbl = QLabel("Статус на системата: Готовност")
        self.status_lbl.setStyleSheet("color: #7f8c8d; font-style: italic;")
        layout.addWidget(self.status_lbl)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d1d1d1;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Свързваме статуса с главния прозорец, за да може другите функции да го обновяват
        self.parent_window.mgmt_status_lbl = self.status_lbl
        self.parent_window.mgmt_progress_bar = self.progress_bar

    # --- ПРЕДПАЗНИ ФУНКЦИИ (WRAPPERS) ---
    
    def safe_dupes(self):
        logging.info("User clicked: Duplicate Manager")
        try:
            # Увери се, че файлът се казва dialog_duplicates.py
            import dialog_duplicates
            dlg = dialog_duplicates.DuplicateManagerDialog(self.parent_window)
            dlg.exec()
            
        except ModuleNotFoundError:
            QMessageBox.critical(self, "Грешка", "Файлът 'dialog_duplicates.py' не е намерен.")
        except Exception as e:
            logging.error(f"Duplicate Manager Error: {e}")
            QMessageBox.warning(self, "Грешка", f"Неуспешно стартиране на мениджъра: {str(e)}")

    def safe_stats(self):
        try: self.parent_window.show_stats()
        except Exception as e: logging.error(f"Stats error: {e}")

    def safe_repair(self):
        try: self.parent_window.run_bulk_update()
        except Exception as e: logging.error(f"Repair error: {e}")

    def safe_import(self):
        try: self.parent_window.handle_import()
        except Exception as e: logging.error(f"Import error: {e}")

    def safe_kindle(self):
        try: self.parent_window.run_kindle_sync_logic()
        except Exception as e: logging.error(f"Kindle Sync error: {e}")

    def safe_backup(self):
        try: 
            # Тъй като сме в облака, тук може да извикаш функция за експорт към CSV
            self.parent_window.run_manual_backup_logic()
        except Exception as e: 
            logging.error(f"Backup error: {e}")
            QMessageBox.information(self, "Инфо", "Функцията за архив се подготвя.")
