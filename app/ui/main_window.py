"""应用协调层：后台执行耗时业务，主线程仅更新 Qt 控件。"""
from datetime import datetime
from pathlib import Path
import logging
import pandas as pd
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtCore import QSize
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QListWidget, QStackedWidget, QProgressBar, QFileDialog, QMessageBox, QInputDialog, QScrollArea)
from app import APP_NAME
from app.core.data_manager import DataManager
from app.core.file_loader import load_file, sheet_names, export_data
from app.core.report_generator import generate_report, export_report
from app.ui.widgets.common import button, NoticeBar
from app.ui.widgets.icons import navigation_icon
from app.ui.widgets.worker import Worker
from app.ui.pages.home_page import HomePage
from app.ui.pages.preview_page import PreviewPage
from app.core.data_query import search_positions
from app.ui.pages.quality_page import QualityPage
from app.ui.pages.cleaning_page import CleaningPage
from app.ui.pages.analysis_page import AnalysisPage
from app.ui.pages.report_page import ReportPage
from app.ui.pages.history_page import HistoryPage
from app.ui.pages.settings_page import SettingsPage
from app.utils.config import ConfigStore


class MainWindow(QMainWindow):
    def __init__(self, config=None):
        super().__init__()
        self.config = config or ConfigStore()
        self.manager = DataManager(self.config.values)
        self.worker = None
        self.busy = False
        self.last_error = ""
        self.last_export = ""
        self.logger = logging.getLogger("dataclean")
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        self.setMinimumSize(1100, 700)
        self.setAcceptDrops(True)
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(202)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 10, 0, 12)
        brand = QLabel("数据清洗与\n质量检测工具软件")
        brand.setObjectName("brand")
        side.addWidget(brand)
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.addItems(["首页", "数据预览", "质量检测", "数据清洗", "数据分析", "检测报告", "操作记录", "设置"])
        self.navigation.setIconSize(QSize(22, 22))
        for index in range(8):
            self.navigation.item(index).setIcon(navigation_icon(index))
        side.addWidget(self.navigation, 1)
        note = QLabel("V1.0  ·  本地工作区\n数据仅在本机处理")
        note.setObjectName("sidebarNote")
        side.addWidget(note)
        root_layout.addWidget(sidebar)
        right = QVBoxLayout()
        right.setSpacing(0)
        top = QFrame()
        top.setObjectName("topbar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(28, 12, 28, 12)
        self.file_label = QLabel("工作区  /  尚未导入数据")
        top_layout.addWidget(self.file_label, 1)
        top_layout.addWidget(button("打开文件", self.open_dialog))
        self.export_button = button("导出数据", self.export_dialog, True)
        top_layout.addWidget(self.export_button)
        right.addWidget(top)
        self.notice = NoticeBar()
        right.addWidget(self.notice)
        self.stack = QStackedWidget()
        self.home, self.preview, self.quality = HomePage(), PreviewPage(), QualityPage()
        self.cleaning, self.analysis = CleaningPage(), AnalysisPage()
        self.report, self.history = ReportPage(), HistoryPage()
        self.settings = SettingsPage(self.config.values, self.config.path)
        for page in [self.home, self.preview, self.quality, self.cleaning, self.analysis, self.report, self.history, self.settings]:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        right.addWidget(self.stack, 1)
        root_layout.addLayout(right, 1)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(160)
        self.statusBar().addPermanentWidget(self.progress)
        self.progress.hide()
        self.statusBar().showMessage("就绪 · 拖入 Excel / CSV 即可开始")
        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.home.open_requested.connect(self.open_dialog)
        self.home.recent_requested.connect(self.open_path)
        self.home.quality_requested.connect(lambda: self.navigation.setCurrentRow(2))
        self.preview.search_requested.connect(self.search)
        self.quality.detect_requested.connect(self.detect)
        self.cleaning.apply_requested.connect(self.apply_clean)
        self.cleaning.undo_requested.connect(self.undo)
        self.report.export_requested.connect(self.export_report_dialog)
        self.history.clear_requested.connect(self.clear_history)
        self.history.export_requested.connect(self.export_history_dialog)
        self.settings.save_requested.connect(self.save_settings)
        QShortcut(QKeySequence.Open, self, activated=self.open_dialog)
        QShortcut(QKeySequence.Undo, self, activated=self.undo)
        self.refresh()
        if self.config.warning:
            self.statusBar().showMessage(self.config.warning)

    def run_job(self, title, function, callback=None, record_failure=True):
        if self.busy:
            return
        self.busy = True
        self.last_error = ""
        self.centralWidget().setEnabled(False)
        self.progress.show()
        self.notice.show_message(title + "…  正在处理数据，请稍候。", "处理中")
        self.statusBar().showMessage(title + "，请稍候…")
        worker = Worker(function, self)
        self.worker = worker
        outcome = {}
        worker.succeeded.connect(lambda result: outcome.update(result=result))
        worker.failed.connect(lambda message, trace: outcome.update(error=message, trace=trace))

        def finished():
            self.worker = None
            self.busy = False
            self.centralWidget().setEnabled(True)
            self.progress.hide()
            self.notice.hide()
            worker.deleteLater()
            if "error" in outcome:
                self.logger.error("%s\n%s", title, outcome["trace"])
                if record_failure:
                    self.manager.record(title, outcome["error"], success=False)
                    self.history.refresh(self.manager)
                self.show_error(outcome["error"])
                return
            try:
                self.statusBar().showMessage(title + "完成", 10000)
                if callback:
                    callback(outcome.get("result"))
            except Exception as exc:
                self.logger.exception("界面更新失败")
                self.show_error(str(exc))
        worker.finished.connect(finished)
        worker.start()

    def show_error(self, message):
        self.last_error = message
        self.statusBar().showMessage("操作未完成：" + message)
        self.notice.show_message("操作未完成  ·  " + message, "严重")

    def confirm(self, title, text):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Question)
        yes = box.addButton("确认", QMessageBox.AcceptRole)
        no = box.addButton("取消", QMessageBox.RejectRole)
        box.setDefaultButton(no)
        box.exec()
        return box.clickedButton() == yes

    def has_data(self):
        if self.busy:
            return False
        if self.manager.original is None:
            self.statusBar().showMessage("请先打开 Excel 或 CSV 文件。", 8000)
            self.notice.show_message("请先打开 Excel 或 CSV 文件，再进行此操作。")
            return False
        return True

    def refresh(self, report_html=None):
        self.home.refresh(self.manager, self.config.values)
        self.preview.refresh(self.manager)
        self.quality.refresh(self.manager)
        self.cleaning.refresh(self.manager, self.config.values)
        self.analysis.refresh(self.manager)
        self.history.refresh(self.manager)
        self.export_button.setEnabled(self.manager.original is not None)
        if report_html is not None:
            self.report.set_report(report_html)
        name = self.manager.metadata.get("name", "尚未导入数据")
        self.file_label.setText("工作区  /  " + (name[:38] + "…" if len(name) > 38 else name) + ("  ·  已清洗" if self.manager.dirty else ""))
        self.file_label.setToolTip(self.manager.metadata.get("path", ""))

    def open_dialog(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, "打开 Excel / CSV", "", "数据文件 (*.xlsx *.xls *.csv)")
        if path:
            self.open_path(path)

    def open_path(self, path):
        if self.busy:
            return
        if self.manager.dirty and not self.confirm("打开新文件", "当前清洗结果尚未导出。打开新文件将清除当前数据和撤销历史，是否继续？"):
            return

        def choose(names):
            sheet = None
            if len(names) > 1:
                sheet, ok = QInputDialog.getItem(self, "选择工作表", "此 Excel 包含多个工作表，请选择：", names, 0, False)
                if not ok:
                    return
            elif names:
                sheet = names[0]
            self.load_path(path, sheet)
        self.run_job("检查文件", lambda: sheet_names(path), choose)

    def load_path(self, path, sheet=None):
        def load():
            frame, metadata = load_file(path, sheet)
            self.manager.load(frame, metadata)
            return generate_report(self.manager)

        def loaded(html):
            try:
                self.config.add_recent(self.manager.metadata["path"])
            except OSError:
                self.logger.exception("最近文件保存失败")
                self.statusBar().showMessage("数据已导入，但最近文件保存失败，请检查配置目录权限。")
            self.refresh(html)
            self.navigation.setCurrentRow(0)
        self.run_job("读取数据并生成质量概览", load, loaded)

    def detect(self):
        if self.has_data():
            def run():
                self.manager.detect(self.config.values)
                return generate_report(self.manager)
            self.run_job("质量检测", run, self.refresh)

    def apply_clean(self, operation, columns, params):
        if not self.has_data():
            return

        def run():
            self.manager.apply(operation, columns, **params)
            return generate_report(self.manager)
        self.run_job(operation, run, self.refresh)

    def undo(self):
        if self.has_data() and len(self.manager.undo):
            def run():
                self.manager.undo_last()
                return generate_report(self.manager)
            self.run_job("撤销清洗", run, self.refresh)

    def search(self, query, column, ascending):
        if self.has_data():
            self.run_job("搜索与排序", lambda: search_positions(self.manager.frame, query, column, ascending), self.preview.set_positions, False)

    def save_settings(self, values):
        def save():
            self.config.save(values)
            if self.manager.original is not None:
                self.manager.detect(self.config.values)
            else:
                self.manager.settings = dict(self.config.values)
                self.manager.undo.set_limit(values["undo_limit"])
            self.manager.record("保存设置", "已保存检测参数与显示偏好")
            return generate_report(self.manager) if self.manager.result else None
        self.run_job("保存设置", save, self.refresh)

    def save_target(self, title, suffix, filters, suggested):
        path, selected_filter = QFileDialog.getSaveFileName(self, title, suggested, filters, options=QFileDialog.DontConfirmOverwrite)
        if not path:
            return None
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(".csv" if "CSV" in selected_filter else suffix)
        if target.exists() and not self.confirm("确认覆盖文件", f"文件已存在：\n{target}\n是否覆盖？"):
            return None
        return target

    def export_dialog(self):
        if not self.has_data():
            return
        source = Path(self.manager.metadata["path"])
        suggested = source.with_name(source.stem + "_cleaned_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".xlsx")
        target = self.save_target("导出清洗后的数据", ".xlsx", "Excel (*.xlsx);;CSV (*.csv)", str(suggested))
        if target:
            self.export_to(target)

    def export_to(self, target):
        def export():
            export_data(self.manager.frame, target, self.manager.metadata.get("path"), allow_overwrite=True)
            self.manager.dirty = False
            self.manager.record("导出数据", str(target), len(self.manager.frame))
            return str(target)

        def done(path):
            self.last_export = path
            self.refresh()
            self.statusBar().showMessage("已导出：" + path)
        self.run_job("导出数据", export, done)

    def export_report_dialog(self):
        if not self.has_data():
            return
        name = Path(self.manager.metadata["name"]).stem + "_质量报告_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".html"
        target = self.save_target("导出 HTML 报告", ".html", "HTML 报告 (*.html)", name)
        if target:
            def export():
                export_report(self.manager, target)
                self.manager.record("导出报告", str(target))
            self.run_job("导出报告", export, lambda _: self.history.refresh(self.manager))

    def export_history_dialog(self):
        target = self.save_target("导出操作记录", ".csv", "CSV (*.csv)", "操作记录_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv")
        if target:
            frame = pd.DataFrame([r.to_dict() for r in self.manager.records], columns=["操作时间", "操作类型", "操作描述", "影响记录数", "影响字段", "是否成功"])
            self.run_job("导出操作记录", lambda: export_data(frame, target, allow_overwrite=True))

    def clear_history(self):
        if self.confirm("清空操作记录", "清空当前会话的操作记录？此操作不改变数据和撤销历史。"):
            self.manager.records.clear()
            self.history.refresh(self.manager)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and not self.busy:
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in (".csv", ".xlsx", ".xls"):
                event.acceptProposedAction()

    def dropEvent(self, event):
        self.open_path(event.mimeData().urls()[0].toLocalFile())
        event.acceptProposedAction()

    def closeEvent(self, event):
        if self.busy:
            self.statusBar().showMessage("正在处理数据，请等待当前任务完成后关闭窗口。")
            event.ignore()
        elif self.manager.dirty and not self.confirm("退出软件", "当前清洗结果尚未导出，确定退出？"):
            event.ignore()
        else:
            event.accept()
