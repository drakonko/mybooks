import logging
import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QFrame, QLabel, QProgressBar, QWidget, 
                             QListWidget, QPushButton, QComboBox, QListWidgetItem, 
                             QInputDialog, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

import database # Вмъкваме базата за синхронизация на целите

def show_stats_dashboard(parent):
    try:
        if parent.all_books_df.empty:
            QMessageBox.information(parent, "Няма данни", "Първо добави книги, за да видиш статистики!")
            return

        stats_dlg = QDialog(parent)
        stats_dlg.setWindowTitle("Reading Insights Dashboard (Cloud Sync)")
        stats_dlg.resize(1150, 900) 
        main_v_layout = QVBoxLayout(stats_dlg)

        # --- ПОДГОТОВКА НА ДАННИТЕ ---
        full_df = parent.all_books_df.copy()
        full_df['rating_int'] = pd.to_numeric(full_df['rating'], errors='coerce').fillna(0).astype(int)
        full_df['year_dt'] = pd.to_datetime(full_df['date_finished'], errors='coerce')
        full_df['finished_year'] = full_df['year_dt'].dt.year
        full_df['pages_num'] = pd.to_numeric(full_df['number_of_pages'], errors='coerce').fillna(0).astype(int)

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        main_v_layout.addWidget(grid_widget)

        # Графики
        fig_genre, ax_genre = plt.subplots()
        canvas_genre = FigureCanvas(fig_genre)
        grid_layout.addWidget(canvas_genre, 0, 0)

        fig_rate, ax_rate = plt.subplots()
        canvas_rate = FigureCanvas(fig_rate)
        grid_layout.addWidget(canvas_rate, 0, 1)

        fig_hist, ax_hist = plt.subplots()
        canvas_hist = FigureCanvas(fig_hist)
        grid_layout.addWidget(canvas_hist, 1, 0)

        # --- КОНТРОЛЕН ЦЕНТЪР ---
        control_card = QFrame()
        control_card.setStyleSheet("background: white; border: 2px solid #3498db; border-radius: 15px; padding: 15px;")
        control_lay = QVBoxLayout(control_card)
        
        y_pick_lay = QHBoxLayout()
        y_pick_lay.addWidget(QLabel("<b>Преглед на година:</b>"))
        year_combo = QComboBox()
        
        current_year = datetime.now().year
        available_years = sorted(full_df['finished_year'].dropna().unique().astype(int).tolist(), reverse=True)
        if current_year not in available_years:
            available_years.insert(0, current_year)
        
        year_combo.addItems([str(y) for y in available_years])
        year_combo.setCurrentText(str(current_year))
        y_pick_lay.addWidget(year_combo)
        control_lay.addLayout(y_pick_lay)

        # Статистика на целта
        self_goal_lbl = QLabel(f"{current_year} Прогрес: 0 / 0")
        self_goal_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        control_lay.addWidget(self_goal_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        
        prog = QProgressBar()
        prog.setFixedHeight(18)
        prog.setStyleSheet("QProgressBar { text-align: center; border-radius: 5px; }")
        control_lay.addWidget(prog)

        # --- СЕКЦИЯ ОБЕМ И РЕКОРДИ ---
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 10px; margin-top: 5px;")
        stats_v_lay = QVBoxLayout(stats_frame)
        
        self_pages_lbl = QLabel("0 Страници")
        self_pages_lbl.setStyleSheet("font-size: 22px; font-weight: 900; color: #8e44ad;")
        self_avg_lbl = QLabel("Средно: 0 стр/ден")
        self_avg_lbl.setStyleSheet("font-size: 12px; color: #7f8c8d; margin-bottom: 5px;")
        
        self_records_lbl = QLabel("<b>Годишни рекорди:</b>")
        self_long_lbl = QLabel("Най-дълга: N/A")
        self_short_lbl = QLabel("Най-кратка: N/A")
        style_rec = "font-size: 11px; color: #34495e;"
        self_long_lbl.setStyleSheet(style_rec)
        self_short_lbl.setStyleSheet(style_rec)

        stats_v_lay.addWidget(self_pages_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        stats_v_lay.addWidget(self_avg_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        stats_v_lay.addWidget(self_records_lbl)
        stats_v_lay.addWidget(self_long_lbl)
        stats_v_lay.addWidget(self_short_lbl)
        control_lay.addWidget(stats_frame)

        btn_view_list = QPushButton("📖 Виж прочетените книги")
        btn_view_list.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 10px; border-radius: 5px; margin-top: 5px;")
        control_lay.addWidget(btn_view_list)

        btn_set_goal = QPushButton("🎯 Настрой цел")
        btn_set_goal.setStyleSheet("background-color: #3498db; color: white; padding: 5px; border-radius: 5px;")
        control_lay.addWidget(btn_set_goal)

        grid_layout.addWidget(control_card, 1, 1)

        def update_dashboard():
            selected_year = int(year_combo.currentText())
            year_df = full_df[(full_df['status'] == 'Read') & (full_df['finished_year'] == selected_year)]
            
            # 1. Обновяване на графиките
            ax_genre.clear()
            genre_counts = year_df['genre'].value_counts()
            if not genre_counts.empty:
                ax_genre.pie(genre_counts, labels=genre_counts.index, autopct='%1.1f%%', startangle=140, colors=plt.cm.Pastel1.colors)
                ax_genre.set_title(f"Жанрове през {selected_year}", fontweight='bold')
            else:
                ax_genre.text(0.5, 0.5, "Няма намерени книги", ha='center')
            canvas_genre.draw()

            ax_rate.clear()
            rate_data = year_df[year_df['rating_int'] > 0]['rating_int'].value_counts().sort_index().reindex(range(1,6), fill_value=0)
            bars = ax_rate.bar([str(r) for r in rate_data.index], rate_data.values, color='#f1c40f')
            ax_rate.bar_label(bars, padding=3)
            ax_rate.set_title(f"Оценки през {selected_year}", fontweight='bold')
            canvas_rate.draw()

            ax_hist.clear()
            monthly_counts = year_df['year_dt'].dt.month.value_counts().sort_index().reindex(range(1,13), fill_value=0)
            month_labels = ['Яну', 'Фев', 'Мар', 'Апр', 'Май', 'Юни', 'Юли', 'Авг', 'Сеп', 'Окт', 'Ное', 'Дек']
            ax_hist.plot(month_labels, monthly_counts.values, marker='o', color='#3498db', linewidth=2)
            ax_hist.set_title(f"Активност през {selected_year}", fontweight='bold')
            ax_hist.grid(True, linestyle='--', alpha=0.3)
            canvas_hist.draw()

            # 2. Синхронизирана цел с основния прозорец
            count = len(year_df)
            # Взимаме целта директно от базата (вече не от JSON)
            goal_val = database.get_yearly_goal() 
            self_goal_lbl.setText(f"{selected_year} Прогрес: {count} / {goal_val} книги")
            
            prog.setMaximum(goal_val)
            prog.setValue(min(goal_val, count))
            
            # Страници
            total_pages = year_df['pages_num'].sum()
            self_pages_lbl.setText(f"{total_pages:,} Страници")
            
            # Скорост
            day_of_year = datetime.now().timetuple().tm_yday if selected_year == datetime.now().year else 365
            avg_daily = total_pages / day_of_year
            self_avg_lbl.setText(f"Скорост: {avg_daily:.1f} стр / ден")

            # 3. Рекорди
            if not year_df.empty:
                page_books = year_df[year_df['pages_num'] > 0]
                if not page_books.empty:
                    longest = page_books.loc[page_books['pages_num'].idxmax()]
                    shortest = page_books.loc[page_books['pages_num'].idxmin()]
                    self_long_lbl.setText(f"🏆 Най-дълга: {longest['title']} ({longest['pages_num']} стр.)")
                    self_short_lbl.setText(f"📜 Най-кратка: {shortest['title']} ({shortest['pages_num']} стр.)")
                else:
                    self_long_lbl.setText("Най-дълга: N/A")
                    self_short_lbl.setText("Най-кратка: N/A")
            else:
                self_long_lbl.setText("Най-дълга: N/A")
                self_short_lbl.setText("Най-кратка: N/A")

        def set_goal():
            year = int(year_combo.currentText())
            # Взимаме текущата цел от облака
            current_g = database.get_yearly_goal(year)
            
            val, ok = QInputDialog.getInt(stats_dlg, "Настройка на цел", f"Цел за {year} г.:", current_g, 1, 1000)
            
            if ok:
                # ЗАПИСВАМЕ В ОБЛАКА (Supabase)
                if database.set_yearly_goal(year, val):
                    update_dashboard() # Опресняваме графиките в Dashboard-а
                    # Обновяваме и лентата в главния прозорец
                    if hasattr(parent, 'progress_bar'):
                        parent.progress_bar.setMaximum(val)
                        parent.display()
                else:
                    QMessageBox.warning(stats_dlg, "Грешка", "Неуспешно записване в облака.")

        def show_list():
            try:
                y_val = int(year_combo.currentText())
                list_dlg = QDialog(stats_dlg); list_dlg.setWindowTitle(f"Прочетени през {y_val}"); list_dlg.resize(600, 500)
                l_lay = QVBoxLayout(list_dlg); list_w = QListWidget(); l_lay.addWidget(list_w)
                
                latest_df = parent.all_books_df.copy()
                latest_df['year_dt'] = pd.to_datetime(latest_df['date_finished'], errors='coerce')
                y_df = latest_df[(latest_df['year_dt'].dt.year == y_val) & (latest_df['status'] == 'Read')]
                
                for _, row in y_df.iterrows():
                    list_w.addItem(f"• {row['title']} ({row['number_of_pages']} стр.)")
                list_dlg.exec()
                update_dashboard()
            except Exception as e: logging.error(e)

        year_combo.currentTextChanged.connect(update_dashboard)
        btn_view_list.clicked.connect(show_list)
        btn_set_goal.clicked.connect(set_goal)
        
        update_dashboard()
        stats_dlg.exec()

    except Exception as e:
        logging.error(f"Dashboard error: {e}")
