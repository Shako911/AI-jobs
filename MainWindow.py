from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QDialog, QMainWindow, QApplication, QTableWidget, QTableWidgetItem, QVBoxLayout, \
    QHBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit, QRadioButton, QFileDialog, \
    QMessageBox, QAbstractItemView
from PyQt5.QtGui import QFont, QDoubleValidator
from PyQt5.QtCore import Qt, pyqtSignal
import sqlite3
import csv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import sys

DB_NAME = "ai_job.db"
TABLE_NAME = "jobs"
ADMIN_PASSWORD = "1234"


def get_connection():
    conn = sqlite3.connect(DB_NAME)

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL UNIQUE,
            category TEXT,
            median_salary REAL,
            ai_risk TEXT,
            description TEXT
        )
    """)
    return conn


class AddJobDialog(QtWidgets.QDialog):
    job_added = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Add New Job")
        self.setFixedSize(400, 300)

        layout = QtWidgets.QFormLayout()

        self.title_input = QtWidgets.QLineEdit()
        self.category_input = QtWidgets.QComboBox()
        self.category_input.addItems(["IT", "Design", "Healthcare", "Education", "Engineering", "Other"])
        self.salary_input = QtWidgets.QLineEdit()
        self.salary_input.setValidator(QtGui.QDoubleValidator(0, 1000000, 2))
        self.risk_input = QtWidgets.QComboBox()
        self.risk_input.addItems(["Low", "Medium", "High"])
        self.desc_input = QtWidgets.QTextEdit()

        layout.addRow("Job Title*:", self.title_input)
        layout.addRow("Category:", self.category_input)
        layout.addRow("Median Salary:", self.salary_input)
        layout.addRow("AI Risk:", self.risk_input)
        layout.addRow("Description:", self.desc_input)

        self.btn = QtWidgets.QPushButton("Add")
        self.btn.clicked.connect(self.add_job)
        layout.addRow(self.btn)
        self.setLayout(layout)

    def add_job(self):
        title = self.title_input.text().strip()
        category = self.category_input.currentText()
        try:
            salary = float(self.salary_input.text())
        except ValueError:
            salary = None
        risk = self.risk_input.currentText()
        desc = self.desc_input.toPlainText().strip()

        if not title:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Job title is required!")
            return

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(f"SELECT 1 FROM {TABLE_NAME} WHERE LOWER(job_title) = LOWER(?)", (title,))
            if cursor.fetchone():
                QtWidgets.QMessageBox.warning(self, "Duplicate", "Job already exists.")
                return
            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} (job_title, category, median_salary, ai_risk, description)
                VALUES (?, ?, ?, ?, ?)
            """, (title, category, salary, risk, desc))
            conn.commit()

            QtWidgets.QMessageBox.information(self, "Success", f"Added '{title}' successfully!")
            self.job_added.emit()
            self.close()

        except sqlite3.OperationalError as e:
            QtWidgets.QMessageBox.critical(self, "Database Error",
                                           f"SQL Error: {e}\nPlease ensure your database schema (table: {TABLE_NAME}) matches the column names: job_title, category, median_salary, ai_risk, description.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")
        finally:
            if conn:
                conn.close()



class EditJobDialog(QtWidgets.QDialog):
    job_updated = QtCore.pyqtSignal()

    def __init__(self, job_id, current_data):
        super().__init__()
        self.job_id = job_id
        self.setWindowTitle("Edit Job")
        self.setFixedSize(400, 300)

        layout = QtWidgets.QFormLayout()

        self.title_input = QtWidgets.QLineEdit(current_data["job_title"])
        self.title_input.setDisabled(True)
        self.category_input = QtWidgets.QComboBox()
        self.category_input.addItems(["IT", "Design", "Healthcare", "Education", "Engineering", "Other"])
        self.category_input.setCurrentText(current_data["category"])

        salary_text = str(current_data["median_salary"]) if current_data["median_salary"] is not None else ""
        self.salary_input = QtWidgets.QLineEdit(salary_text)
        self.salary_input.setValidator(QtGui.QDoubleValidator(0, 1000000, 2))

        self.risk_input = QtWidgets.QComboBox()
        self.risk_input.addItems(["Low", "Medium", "High"])
        self.risk_input.setCurrentText(current_data["ai_risk"])
        self.desc_input = QtWidgets.QTextEdit(current_data["description"])

        layout.addRow("Job Title:", self.title_input)
        layout.addRow("Category:", self.category_input)
        layout.addRow("Median Salary:", self.salary_input)
        layout.addRow("AI Risk:", self.risk_input)
        layout.addRow("Description:", self.desc_input)

        self.btn = QtWidgets.QPushButton("Update")
        self.btn.clicked.connect(self.update_job)
        layout.addRow(self.btn)
        self.setLayout(layout)

    def update_job(self):
        category = self.category_input.currentText()
        try:
            salary = float(self.salary_input.text())
        except ValueError:
            salary = None
        risk = self.risk_input.currentText()
        desc = self.desc_input.toPlainText().strip()

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE {TABLE_NAME} SET
                    category = ?,
                    median_salary = ?,
                    ai_risk = ?,
                    description = ?
                WHERE id = ?
            """, (category, salary, risk, desc, self.job_id))
            conn.commit()

            QtWidgets.QMessageBox.information(self, "Updated", "Job updated successfully.")
            self.job_updated.emit()
            self.close()

        except sqlite3.OperationalError as e:
            QtWidgets.QMessageBox.critical(self, "Database Error",
                                           f"SQL Error: {e}\nPlease ensure your database schema (table: {TABLE_NAME}) matches the column names.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")
        finally:
            if conn:
                conn.close()



class InfoWindow(QtWidgets.QWidget):
    def __init__(self, job_data):
        super().__init__()
        self.setWindowTitle("Job Information")
        self.setGeometry(100, 100, 500, 300)
        layout = QtWidgets.QVBoxLayout()

        job_text = f"""
        <b>Job Title:</b> {job_data["job_title"]}<br>
        <b>Category:</b> {job_data["category"]}<br>
        <b>Median Salary:</b> {job_data["median_salary"] if job_data["median_salary"] is not None else 'N/A'}<br>
        <b>AI Risk:</b> {job_data["ai_risk"]}<br>
        <b>Description:</b> {job_data["description"] if job_data["description"] else 'No description available.'}
        """
        label = QtWidgets.QLabel(job_text)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 14px; color: black;")
        layout.addWidget(label)
        self.setLayout(layout)



class ChartWindow(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Risk Distribution by Salary")
        self.setGeometry(100, 100, 700, 500)

        self.figure, self.ax = plt.subplots(figsize=(7, 4))
        self.canvas = FigureCanvas(self.figure)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.plot_chart()

    def plot_chart(self):
        risk_data = {"Low": 0.0, "Medium": 0.0, "High": 0.0}

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT ai_risk, median_salary FROM {TABLE_NAME}")
            rows = cursor.fetchall()

            for risk, salary in rows:
                if risk in risk_data and salary is not None:
                    risk_data[risk] += salary

            self.ax.clear()

            risks = list(risk_data.keys())
            salaries = [risk_data[risk] for risk in risks]

            self.ax.bar(risks, salaries, color=['#4CAF50', '#FFC107', '#F44336'])
            self.ax.set_xlabel("AI Risk", fontsize=12)
            self.ax.set_ylabel("Total Salary", fontsize=12)
            self.ax.set_title("AI Risk Distribution by Salary", fontsize=14)
            self.ax.set_ylim(bottom=0)

            for i, v in enumerate(salaries):
                if v > 0:
                    self.ax.text(i, v + (self.ax.get_ylim()[1] * 0.02), f"{v:.1f}", ha='center', va='bottom',
                                 fontsize=10)

            self.figure.tight_layout()
            self.canvas.draw()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Chart Error", f"Failed to load chart data: {e}")
        finally:
            if conn:
                conn.close()



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Job Explorer")
        self.resize(800, 600)
        self.setStyleSheet("background-color: rgb(30, 30, 30);")

        self.centralwidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.centralwidget)
        self.main_layout = QtWidgets.QVBoxLayout(self.centralwidget)

        self._setup_ui_elements()
        self._setup_table_and_buttons()
        self.refresh_job_list()

    def _setup_ui_elements(self):

        self.label = QtWidgets.QLabel("Will AI Take Your Job?", self.centralwidget)
        self.label.setFont(QtGui.QFont("Arial", 16))
        self.label.setStyleSheet("color: white;")
        self.label.setAlignment(QtCore.Qt.AlignCenter)

        self.label_2 = QtWidgets.QLabel("Search your job and find out", self.centralwidget)
        self.label_2.setFont(QtGui.QFont("Arial", 9))
        self.label_2.setStyleSheet("color: white;")
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)

        self.main_layout.addWidget(self.label)
        self.main_layout.addWidget(self.label_2)


        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addStretch()

        self.label_3 = QtWidgets.QLabel("Choose Profession", self.centralwidget)
        self.label_3.setFont(QtGui.QFont("Arial", 10))
        self.label_3.setStyleSheet("color: white;")
        search_layout.addWidget(self.label_3)

        self.comboBox = QtWidgets.QComboBox(self.centralwidget)
        self.comboBox.setEditable(True)
        self.comboBox.setStyleSheet("color: black; background-color: white;")

        self._populate_job_titles_combo_box()
        self.comboBox.setPlaceholderText("Select or type a job title...")
        search_layout.addWidget(self.comboBox)

        self.pushButton_search = QtWidgets.QPushButton("Search", self.centralwidget)
        self.pushButton_search.setFont(QtGui.QFont("Arial", 10))
        self.pushButton_search.setStyleSheet("background-color: lightgray; color: black;")
        self.pushButton_search.clicked.connect(self.search_job)
        search_layout.addWidget(self.pushButton_search)
        search_layout.addStretch()

        self.main_layout.addLayout(search_layout)


        self.label_admin_info = QtWidgets.QLabel(
            "If you want to Add/Edit/Delete profession, you need administrator privileges.", self.centralwidget)
        self.label_admin_info.setFont(QtGui.QFont("Arial", 10))
        self.label_admin_info.setStyleSheet("color: white;")
        self.label_admin_info.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(self.label_admin_info)

        admin_check_layout = QtWidgets.QHBoxLayout()
        admin_check_layout.addStretch()
        self.radioButton_permission = QtWidgets.QRadioButton("I have permission", self.centralwidget)
        self.radioButton_permission.setStyleSheet("color: white;")
        self.radioButton_permission.toggled.connect(self.toggle_admin_ui)
        admin_check_layout.addWidget(self.radioButton_permission)
        admin_check_layout.addStretch()
        self.main_layout.addLayout(admin_check_layout)


        password_layout = QtWidgets.QHBoxLayout()
        password_layout.addStretch()
        self.password_input = QtWidgets.QLineEdit(self.centralwidget)
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setStyleSheet("color: black; background-color: white;")
        self.password_input.hide()
        password_layout.addWidget(self.password_input)

        self.check_button = QtWidgets.QPushButton("Check", self.centralwidget)
        self.check_button.setStyleSheet("color: white; background-color: #007BFF;")
        self.check_button.clicked.connect(self.verify_password)
        self.check_button.hide()
        password_layout.addWidget(self.check_button)
        password_layout.addStretch()
        self.main_layout.addLayout(password_layout)

        self.label_password_status = QtWidgets.QLabel("", self.centralwidget)
        self.label_password_status.setStyleSheet("color: white;")
        self.label_password_status.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(self.label_password_status)


        admin_buttons_layout = QtWidgets.QHBoxLayout()
        self.pushButton_add = QtWidgets.QPushButton("Add", self.centralwidget)
        self.pushButton_add.setStyleSheet("background-color: #28A745; color: white;")
        self.pushButton_add.clicked.connect(self.add_job)
        self.pushButton_add.setEnabled(False)
        admin_buttons_layout.addWidget(self.pushButton_add)

        self.pushButton_edit = QtWidgets.QPushButton("Edit", self.centralwidget)
        self.pushButton_edit.setStyleSheet("background-color: #FFC107; color: black;")
        self.pushButton_edit.clicked.connect(self.edit_job)
        self.pushButton_edit.setEnabled(False)
        admin_buttons_layout.addWidget(self.pushButton_edit)

        self.pushButton_delete = QtWidgets.QPushButton("Delete", self.centralwidget)
        self.pushButton_delete.setFont(QtGui.QFont("MS Shell Dlg 2", 10))
        self.pushButton_delete.setStyleSheet("background-color: #DC3545; color: white;")
        self.pushButton_delete.clicked.connect(self.delete_job)
        self.pushButton_delete.setEnabled(False)
        admin_buttons_layout.addWidget(self.pushButton_delete)

        self.main_layout.addLayout(admin_buttons_layout)
        self.main_layout.addStretch()

    def _setup_table_and_buttons(self):

        self.table = QtWidgets.QTableWidget(self.centralwidget)
        self.table.setColumnCount(5)

        self.table.setHorizontalHeaderLabels(["ID", "Job Title", "Category", "Median Salary", "AI Risk"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet("background-color: white; color: black;")
        self.main_layout.addWidget(self.table)


        bottom_buttons_layout = QtWidgets.QHBoxLayout()
        bottom_buttons_layout.addStretch()

        self.pushButton_chart = QtWidgets.QPushButton("Show Chart", self.centralwidget)
        self.pushButton_chart.setStyleSheet("background-color: #17A2B8; color: white;")
        self.pushButton_chart.clicked.connect(self.open_chart)
        bottom_buttons_layout.addWidget(self.pushButton_chart)

        self.pushButton_export_pdf = QtWidgets.QPushButton("Export PDF", self.centralwidget)
        self.pushButton_export_pdf.setStyleSheet("background-color: #6C757D; color: white;")
        self.pushButton_export_pdf.clicked.connect(self.export_pdf)
        bottom_buttons_layout.addWidget(self.pushButton_export_pdf)

        self.pushButton_export_csv = QtWidgets.QPushButton("Export CSV", self.centralwidget)
        self.pushButton_export_csv.setStyleSheet("background-color: #6C757D; color: white;")
        self.pushButton_export_csv.clicked.connect(self.export_csv)
        bottom_buttons_layout.addWidget(self.pushButton_export_csv)
        bottom_buttons_layout.addStretch()

        self.main_layout.addLayout(bottom_buttons_layout)

    def _populate_job_titles_combo_box(self):

        self.comboBox.clear()
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(f'SELECT job_title FROM {TABLE_NAME} ORDER BY job_title')
            job_titles = [row[0] for row in cursor.fetchall()]
            self.comboBox.addItems(job_titles)
        except Exception as e:
            print(f"Error populating combo box: {e}")
        finally:
            if conn:
                conn.close()

    def refresh_job_list(self):

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, job_title, category, median_salary, ai_risk FROM {TABLE_NAME}")
            rows = cursor.fetchall()

            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    item = QtWidgets.QTableWidgetItem(str(val) if val is not None else "N/A")
                    self.table.setItem(r, c, item)
            self.table.resizeColumnsToContents()
            self.table.horizontalHeader().setStretchLastSection(True)
            self._populate_job_titles_combo_box()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Database Error", f"Failed to refresh job list: {e}")
        finally:
            if conn:
                conn.close()

    def search_job(self):

        search_term = self.comboBox.currentText().strip()
        if not search_term:
            QtWidgets.QMessageBox.warning(self, "Search Error", "Please enter a job title to search.")
            return

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                f"SELECT job_title, category, median_salary, ai_risk, description FROM {TABLE_NAME} WHERE LOWER(job_title) = LOWER(?)",
                (search_term,))
            job_data_raw = cursor.fetchone()

            if job_data_raw:

                job_data = {
                    "job_title": job_data_raw[0],
                    "category": job_data_raw[1],
                    "median_salary": job_data_raw[2],
                    "ai_risk": job_data_raw[3],
                    "description": job_data_raw[4] if job_data_raw[4] is not None else ""
                }
                self.info_window = InfoWindow(job_data)
                self.info_window.show()
            else:
                QtWidgets.QMessageBox.information(self, "Not Found", f"Job '{search_term}' not found in the database.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred during search: {e}")
        finally:
            if conn:
                conn.close()

    def add_job(self):

        dlg = AddJobDialog()
        dlg.job_added.connect(self.refresh_job_list)
        dlg.exec_()

    def edit_job(self):

        sel_row = self.table.currentRow()
        if sel_row < 0:
            QtWidgets.QMessageBox.warning(self, "No selection", "Select a job to edit.")
            return


        job_id_item = self.table.item(sel_row, 0)
        if job_id_item is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Could not retrieve job ID for editing.")
            return

        try:
            job_id = int(job_id_item.text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Error", "Invalid Job ID.")
            return


        current_data = {}
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT job_title, category, median_salary, ai_risk, description FROM {TABLE_NAME} WHERE id = ?",
                (job_id,))
            data_row = cursor.fetchone()

            if data_row:
                current_data = {
                    "job_title": data_row[0],
                    "category": data_row[1],
                    "median_salary": data_row[2],
                    "ai_risk": data_row[3],
                    "description": data_row[4] if data_row[4] is not None else ""
                }
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "Job data not found for editing.")
                return
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Database Error", f"Failed to fetch job data for editing: {e}")
            return
        finally:
            if conn:
                conn.close()

        dlg = EditJobDialog(job_id, current_data)
        dlg.job_updated.connect(self.refresh_job_list)
        dlg.exec_()

    def delete_job(self):

        sel_row = self.table.currentRow()
        if sel_row < 0:
            QtWidgets.QMessageBox.warning(self, "No selection", "Select a job to delete.")
            return


        job_id_item = self.table.item(sel_row, 0)
        job_title_display = self.table.item(sel_row, 1).text()
        if job_id_item is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Could not retrieve job ID for deletion.")
            return

        try:
            job_id = int(job_id_item.text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Error", "Invalid Job ID selected for deletion.")
            return

        reply = QtWidgets.QMessageBox.question(self, "Confirm Deletion",
                                               f"Are you sure you want to delete '{job_title_display}' (ID: {job_id})?",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE id = ?", (job_id,))
                conn.commit()
                QtWidgets.QMessageBox.information(self, "Deleted", f"'{job_title_display}' deleted successfully!")
                self.refresh_job_list()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to delete job: {e}")
            finally:
                if conn:
                    conn.close()

    def open_chart(self):
        self.chart_win = ChartWindow()
        self.chart_win.show()

    def export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save CSV", "ai_jobs_report.csv", "CSV Files (*.csv)")
        if path:
            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(f"SELECT job_title, category, median_salary, ai_risk, description FROM {TABLE_NAME}")
                exported_data = cursor.fetchall()
                with open(path, "w", newline='', encoding="utf-8") as file:
                    writer = csv.writer(file)
                    writer.writerow(["Job Title", "Category", "Median Salary", "AI Risk", "Description"])
                    writer.writerows(exported_data)
                QtWidgets.QMessageBox.information(self, "Success", f"Data exported to CSV:\n{path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to export CSV: {e}")
            finally:
                if conn:
                    conn.close()

    def export_pdf(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save PDF", "ai_jobs_report.pdf", "PDF Files (*.pdf)")
        if path:
            try:
                self._generate_pdf_report(path)
                QtWidgets.QMessageBox.information(self, "Success", f"Report exported to PDF:\n{path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to export PDF: {e}")

    def _generate_pdf_report(self, path):
        c = canvas.Canvas(path, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, "AI Job Risk Report")

        y = height - 100
        row_height = 20

        headers = ["Job Title", "Category", "Median Salary", "AI Risk"]
        col_widths = [200, 100, 100, 80]

        x_offset = 50
        c.setFont("Helvetica-Bold", 10)
        for i, header in enumerate(headers):
            c.drawString(x_offset, y, header)
            x_offset += col_widths[i]

        y -= row_height
        c.line(50, y, width - 50, y)
        y -= 10

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT job_title, category, median_salary, ai_risk FROM {TABLE_NAME}")
            jobs = cursor.fetchall()

            c.setFont("Helvetica", 9)
            for job in jobs:
                if y < 50:
                    c.showPage()
                    c.setFont("Helvetica-Bold", 16)
                    c.drawString(50, height - 50, "AI Job Risk Report (continued)")
                    y = height - 100
                    x_offset = 50
                    c.setFont("Helvetica-Bold", 10)
                    for i, header in enumerate(headers):
                        c.drawString(x_offset, y, header)
                        x_offset += col_widths[i]
                    y -= row_height
                    c.line(50, y, width - 50, y)
                    y -= 10
                    c.setFont("Helvetica", 9)

                x_offset = 50
                for i, data_item in enumerate(job):
                    display_data = str(data_item) if data_item is not None else "N/A"

                    if i in [0, 1] and c.stringWidth(display_data, "Helvetica", 9) > col_widths[i] - 5:
                        lines = []
                        current_line = []
                        words = display_data.split(' ')
                        for word in words:
                            if c.stringWidth(' '.join(current_line + [word]), "Helvetica", 9) < col_widths[i] - 5:
                                current_line.append(word)
                            else:
                                lines.append(' '.join(current_line))
                                current_line = [word]
                        lines.append(' '.join(current_line))

                        text_y = y
                        for line_part in lines:
                            c.drawString(x_offset, text_y, line_part)
                            text_y -= 10
                        if len(lines) > 1:
                            y -= (len(lines) - 1) * 10
                    else:
                        c.drawString(x_offset, y, display_data)
                    x_offset += col_widths[i]
                y -= row_height
        except Exception as e:
            raise Exception(f"Error generating PDF content: {e}")
        finally:
            if conn:
                conn.close()
        c.save()

    def toggle_admin_ui(self):

        is_checked = self.radioButton_permission.isChecked()
        self.password_input.setVisible(is_checked)
        self.check_button.setVisible(is_checked)
        self.label_password_status.setText("")
        self.password_input.clear()


        if not is_checked:
            self.pushButton_add.setEnabled(False)
            self.pushButton_edit.setEnabled(False)
            self.pushButton_delete.setEnabled(False)

    def verify_password(self):

        if self.password_input.text() == ADMIN_PASSWORD:
            self.label_password_status.setText("✅ Access granted")
            self.label_password_status.setStyleSheet("color: #28A745;")
            self.password_input.hide()
            self.check_button.hide()

            self.pushButton_add.setEnabled(True)
            self.pushButton_edit.setEnabled(True)
            self.pushButton_delete.setEnabled(True)
        else:
            self.label_password_status.setText("❌ Wrong password")
            self.label_password_status.setStyleSheet("color: #DC3545;")
            self.password_input.clear()
            self.password_input.setFocus()


            self.pushButton_add.setEnabled(False)
            self.pushButton_edit.setEnabled(False)
            self.pushButton_delete.setEnabled(False)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())