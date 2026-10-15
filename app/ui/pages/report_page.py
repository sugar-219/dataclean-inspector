from PySide6.QtWidgets import QTextBrowser, QHBoxLayout
from PySide6.QtCore import Signal
from app.ui.widgets.common import Page, button


class ReportPage(Page):
    export_requested = Signal()

    def __init__(self):
        super().__init__("检测报告", "报告包含评分组成、字段质量、主要问题、清洗建议与前后对比。")
        row = QHBoxLayout()
        row.addWidget(button("导出 HTML 检测报告", self.export_requested.emit, True))
        row.addStretch()
        self.layout.addLayout(row)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml("<h2>尚未生成报告</h2><p>导入数据后自动生成；每次清洗都会更新。</p>")
        self.layout.addWidget(self.browser, 1)

    def set_report(self, html):
        self.browser.setHtml(html)
