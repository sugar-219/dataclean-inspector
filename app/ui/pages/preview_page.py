import numpy as np
import pandas as pd
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QLabel, QSplitter
from PySide6.QtCore import Qt, Signal
from app.ui.widgets.common import Page, button
from app.ui.widgets.data_table import DataTable


class PreviewPage(Page):
    search_requested = Signal(str, int, bool)

    def __init__(self):
        super().__init__("数据预览", "搜索与排序仅改变显示顺序；左侧行号始终对应当前数据的位置。")
        self.frame = pd.DataFrame()
        self.positions = np.array([], dtype=int)
        self.page = 0
        self.page_size = 500
        self.sort_column = -1
        self.ascending = True
        self.info = QLabel("尚未导入数据")
        self.layout.addWidget(self.info)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索任意字段（不区分大小写，按回车执行）")
        self.search.returnPressed.connect(self.request_search)
        row.addWidget(self.search, 1)
        row.addWidget(button("搜索", self.request_search, True))
        row.addWidget(button("清除", self.clear_search))
        self.layout.addLayout(row)
        splitter = QSplitter(Qt.Vertical)
        self.table = DataTable()
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().sectionClicked.connect(self.sort)
        self.fields = DataTable(formatted=True, empty_text="字段信息\n导入后展示类型、缺失率与唯一值数量。")
        splitter.addWidget(self.table)
        splitter.addWidget(self.fields)
        splitter.setSizes([360, 160])
        self.layout.addWidget(splitter, 1)
        pagination = QHBoxLayout()
        self.previous = button("上一页", lambda: self.change_page(-1))
        self.next = button("下一页", lambda: self.change_page(1))
        self.page_label = QLabel()
        pagination.addWidget(self.previous)
        pagination.addWidget(self.page_label)
        pagination.addWidget(self.next)
        pagination.addStretch()
        pagination.addWidget(QLabel("每页 500 行 · 下方为字段信息"))
        self.layout.addLayout(pagination)

    def refresh(self, manager):
        self.frame = manager.frame
        self.positions = np.arange(len(self.frame))
        self.page, self.sort_column = 0, -1
        self.search.clear()
        self.table.horizontalHeader().setSortIndicatorShown(False)
        meta = manager.metadata
        self.info.setText(f"{meta.get('name', '尚未导入')}    {len(self.frame):,} 行 × {len(self.frame.columns)} 列    文件大小 {meta.get('size', 0) / 1024:.1f} KB")
        self.fields.set_frame(manager.result.fields if manager.result else pd.DataFrame())
        self.render()

    def request_search(self):
        self.search_requested.emit(self.search.text(), self.sort_column, self.ascending)

    def clear_search(self):
        self.search.clear()
        self.sort_column = -1
        self.request_search()

    def sort(self, column):
        self.ascending = not self.ascending if self.sort_column == column else True
        self.sort_column = column
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().setSortIndicator(column, Qt.AscendingOrder if self.ascending else Qt.DescendingOrder)
        self.request_search()

    def set_positions(self, positions):
        self.positions, self.page = positions, 0
        self.table.empty.setText("没有找到匹配的数据\n尝试其他关键词，或点击“清除”恢复全部记录。" if self.search.text() else "暂无数据\n打开 Excel 或 CSV 后在这里查看内容")
        self.render()

    def change_page(self, delta):
        self.page += delta
        self.render()

    def render(self):
        pages = max(1, (len(self.positions) + self.page_size - 1) // self.page_size)
        self.page = max(0, min(self.page, pages - 1))
        self.table.set_frame(self.frame, self.positions[self.page * self.page_size:(self.page + 1) * self.page_size])
        self.page_label.setText(f"第 {self.page + 1} / {pages} 页，共 {len(self.positions):,} 行")
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < pages - 1)
