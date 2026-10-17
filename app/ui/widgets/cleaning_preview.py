"""清洗确认窗口：只有确认后才应用候选数据。"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout
from app.core.cleaning_preview import PREVIEW_LIMIT
from app.ui.widgets.common import button, muted, section_title
from app.ui.widgets.data_table import DataTable


class CleaningPreviewDialog(QDialog):
    def __init__(self, before, change, samples, parent=None):
        super().__init__(parent)
        self.setWindowTitle("清洗前预览")
        self.resize(900, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(section_title("确认本次清洗"))
        layout.addWidget(muted(change.description))
        self.summary = muted(
            f"影响 {change.affected:,} 条记录    ·    "
            f"{len(before):,} 行 × {len(before.columns)} 列 → "
            f"{len(change.frame):,} 行 × {len(change.frame.columns)} 列")
        layout.addWidget(self.summary)
        self.table = DataTable(samples, empty_text="本次操作没有值或字段结构变化。")
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 260)
        self.table.setColumnWidth(3, 260)
        layout.addWidget(self.table, 1)
        layout.addWidget(muted(
            f"最多展示 {PREVIEW_LIMIT} 条改动样例；引号用于显示文本及首尾空格。"
            "数据行号对应清洗前的数据，不包含表头；类型转换也可能列出内容相同的记录。"))
        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_button = button("取消", self.reject)
        self.cancel_button.setDefault(True)
        actions.addWidget(self.cancel_button)
        self.apply_button = button("确认应用", self.accept, True)
        self.apply_button.setAutoDefault(False)
        self.apply_button.setEnabled(not before.equals(change.frame))
        actions.addWidget(self.apply_button)
        layout.addLayout(actions)
