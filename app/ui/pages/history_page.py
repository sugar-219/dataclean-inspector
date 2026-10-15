import pandas as pd
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtCore import Signal
from app.ui.widgets.common import Page, button
from app.ui.widgets.data_table import DataTable


class HistoryPage(Page):
    clear_requested = Signal()
    export_requested = Signal()

    def __init__(self):
        super().__init__("操作记录", "记录本次会话的导入、检测、清洗、撤销、导出及失败原因。")
        row = QHBoxLayout()
        row.addWidget(button("导出操作记录", self.export_requested.emit, True))
        row.addWidget(button("清空记录", self.clear_requested.emit))
        row.addStretch()
        self.layout.addLayout(row)
        self.table = DataTable(status_columns=("是否成功",), empty_text="暂无操作记录\n导入、检测、清洗和导出的结果将在这里记录。")
        self.layout.addWidget(self.table, 1)

    def refresh(self, manager):
        self.table.set_frame(pd.DataFrame([r.to_dict() for r in manager.records], columns=["操作时间", "操作类型", "操作描述", "影响记录数", "影响字段", "是否成功"]))
