import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QSpinBox, QComboBox, QHeaderView,
    QCompleter, QProgressBar
)
from collector import HHCollector
from extractor import SkillExtractor
from importance import SkillWeightAnalyzer
from matcher import SkillMatcher
from cleaner import TextCleaner
from normalizer import SkillNormalizer
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtCore import Qt
from PySide6.QtCore import QObject, Signal
from PySide6.QtCore import QThread

class AnalyzeWorker(QObject):
    """
    Класс запускает анализ навыков пользователя и вакансий в отдельном потоке.
    """
    progress = Signal(int)
    finished = Signal(list)

    def __init__(self, vacancies, user_skills, nlp, skill_weighter, matcher):
        super().__init__()
        self.vacancies = vacancies
        self.user_skills = user_skills
        self.nlp = nlp
        self.skill_weighter = skill_weighter
        self.matcher = matcher

    def run(self):
        results = []
        total = len(self.vacancies)

        for i, vacancy in enumerate(self.vacancies):
            job_skills = self.skill_weighter.extract_weighted_skills(vacancy["description"], self.nlp)
            if job_skills:
                result = self.matcher.match_skills(self.user_skills, job_skills)
                results.append((vacancy, result))

            self.progress.emit(int((i + 1) / total * 100))

        results.sort(key=lambda x: x[1]["match_score"], reverse=True)
        self.finished.emit(results)

class CollectWorker(QObject):
    """
    Класс запускает процесс сбора данных с API в отдельном потоке.
    """
    progress = Signal(int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, collector, cleaner, query, limit, area_id):
        super().__init__()
        self.collector = collector
        self.cleaner = cleaner
        self.query = query
        self.limit = limit
        self.area_id = area_id

    def run(self):
        try:
            vacancies = self.collector.collect(
                self.query,
                limit=self.limit,
                area=self.area_id,
                progress_callback=lambda p: self.progress.emit(p)
            )

            for vacancy in vacancies:
                vacancy["description"] = self.cleaner.clean_html(vacancy["description"])

            self.finished.emit(vacancies)

        except Exception as e:
            self.error.emit(str(e))

class SkillMatcherApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Internship Skill Analyzer")
        self.resize(1000, 600)
        self.normalizer = SkillNormalizer()
        self.extractor = SkillExtractor("./custom_ner_lg", self.normalizer)
        self.nlp = self.extractor.load_model()
        self.collector = HHCollector()
        self.cleaner = TextCleaner()
        self.skill_weighter = SkillWeightAnalyzer(self.extractor, self.normalizer)
        self.matcher = SkillMatcher()

        layout = QVBoxLayout()

        # Поисковая панель
        search_row = QHBoxLayout()

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Поисковый запрос (например: Python backend)")
        self.query_input.setMinimumWidth(250)
        search_row.addWidget(self.query_input)

        self.area_combo = QComboBox()
        self.area_combo.setEditable(True)
        self.area_combo.setMinimumWidth(180)

        areas_raw = self.collector.get_areas()
        self.area_dict = self.flatten_areas(areas_raw)

        self.area_combo.addItem("")  # Пустой выбор
        self.area_combo.addItems(sorted(self.area_dict.keys()))

        completer = QCompleter(self.area_dict.keys())
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.area_combo.setCompleter(completer)

        search_row.addWidget(self.area_combo)

        self.limit_input = QSpinBox()
        self.limit_input.setMinimum(1)
        self.limit_input.setMaximum(5000)
        self.limit_input.setValue(50)
        search_row.addWidget(QLabel("Количество:"))
        search_row.addWidget(self.limit_input)

        self.load_button = QPushButton("Загрузить")
        self.load_button.clicked.connect(self.load_vacancies)
        search_row.addWidget(self.load_button)

        skills_row = QHBoxLayout()

        self.user_skills_input = QLineEdit()
        self.user_skills_input.setPlaceholderText("Ваши навыки через запятую (например: Python, SQL, Git)")
        skills_row.addWidget(self.user_skills_input)

        self.analyze_button = QPushButton("Анализировать навыки")
        self.analyze_button.clicked.connect(self.analyze_loaded)
        skills_row.addWidget(self.analyze_button)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.loaded_vacancies = []
        layout.addLayout(search_row)
        layout.addLayout(skills_row)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Оценка",
            "Название",
            "Компания",
            "Регион",
            "Совпало",
            "Не хватает",
            "Ссылка"
        ])
        header = self.table.horizontalHeader()

        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Score
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Компания
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Регион
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Ссылка

        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 220)

        header.setSectionResizeMode(4, QHeaderView.Stretch)  # Совпало
        header.setSectionResizeMode(5, QHeaderView.Stretch)  # Не хватает

        self.table.setWordWrap(True)

        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)
        self.table.cellClicked.connect(self.open_link)

        self.setLayout(layout)

    def load_vacancies(self):
        limit = self.limit_input.value()
        query = self.query_input.text().strip()
        area_name = self.area_combo.currentText().strip()
        area_id = self.area_dict.get(area_name)

        self.progress.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.load_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.load_button.setEnabled(False)

        self.thread = QThread()
        self.worker = CollectWorker(
            self.collector,
            self.cleaner,
            query,
            limit,
            area_id
        )

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.on_collect_finished)
        self.worker.error.connect(self.on_collect_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_collect_finished(self, vacancies):
        self.loaded_vacancies = vacancies

        self.progress.setValue(100)
        self.progress.setVisible(False)

        self.load_button.setEnabled(True)
        self.analyze_button.setEnabled(True)

    def on_collect_error(self, message):
        print("Ошибка:", message)
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.load_button.setEnabled(True)

    def analyze_loaded(self):
        user_text = self.user_skills_input.text().strip()
        if not self.loaded_vacancies:
            return

        self.table.setRowCount(0)
        user_skills = self.extractor.get_user_skills(user_text)

        self.thread = QThread()
        self.worker = AnalyzeWorker(
            self.loaded_vacancies,
            user_skills,
            self.nlp,
            self.skill_weighter,
            self.matcher
        )

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.on_analysis_finished)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.load_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.thread.start()

    def on_analysis_finished(self, results):
        self.table.setSortingEnabled(False)

        for vacancy, result in results:
            self.add_row(vacancy, result)

        self.table.setSortingEnabled(True)

        self.progress.setValue(100)
        self.progress.setVisible(False)

        self.load_button.setEnabled(True)
        self.analyze_button.setEnabled(True)

    def open_link(self, row, column):
        if column == 6:
            item = self.table.item(row, column)
            if item:
                url = item.data(Qt.ItemDataRole.UserRole)
                if url:
                    QDesktopServices.openUrl(QUrl(url))

    def add_row(self, vacancy, result):
        row = self.table.rowCount()
        self.table.insertRow(row)
        score_item = QTableWidgetItem()
        score_item.setData(Qt.ItemDataRole.DisplayRole, result['match_score'] * 100)
        score_item.setText(f"{result['match_score'] * 100:.1f}%")

        self.table.setItem(row, 0, score_item)
        self.table.setItem(row, 1, QTableWidgetItem(vacancy["title"] or ""))
        self.table.setItem(row, 2, QTableWidgetItem(vacancy["company"] or ""))
        self.table.setItem(row, 3, QTableWidgetItem(vacancy["area"] or ""))
        matched_item = QTableWidgetItem(", ".join(result["matched"]))
        matched_item.setToolTip("\n".join(result["matched"]))
        self.table.setItem(row, 4, matched_item)

        missing_item = QTableWidgetItem(", ".join(result["missing"]))
        missing_item.setToolTip("\n".join(result["missing"]))
        self.table.setItem(row, 5, missing_item)
        url = f"https://hh.ru/vacancy/{vacancy['id']}"

        link_item = QTableWidgetItem("Открыть")
        link_item.setData(Qt.ItemDataRole.UserRole, url)
        link_item.setForeground(Qt.GlobalColor.blue)

        self.table.setItem(row, 6, link_item)

    def flatten_areas(self, areas):
        result = {}

        def recurse(area_list):
            for area in area_list:
                result[area["name"]] = area["id"]
                if area.get("areas"):
                    recurse(area["areas"])

        recurse(areas)
        return result

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SkillMatcherApp()
    window.show()
    sys.exit(app.exec())