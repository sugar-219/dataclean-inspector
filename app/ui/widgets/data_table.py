"""按需读取 DataFrame 的 Qt Model，不创建逐单元格控件。"""
import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QTableView, QHeaderView, QLabel, QStyledItemDelegate, QStyle
from PySide6.QtGui import QColor, QPainter
from numbers import Real
from app.utils.helpers import display_value


class DataFrameModel(QAbstractTableModel):
    def __init__(self, frame=None, parent=None):
        super().__init__(parent)
        self.frame = frame if frame is not None else pd.DataFrame()
        self.positions = np.arange(len(self.frame))
        self.format_numbers = False

    def set_frame(self, frame, positions=None):
        self.beginResetModel()
        self.frame = frame
        self.positions = np.asarray(positions) if positions is not None else np.arange(len(frame))
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.positions)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            raw = self.frame.iloc[int(self.positions[index.row()]), index.column()]
            value = display_value(raw)
            if role == Qt.DisplayRole and self.format_numbers and isinstance(raw, Real) and not pd.isna(raw):
                if self.frame.columns[index.column()] == "缺失率":
                    return f"{raw:.1%}"
                return f"{raw:,.4f}".rstrip("0").rstrip(".") if raw % 1 else f"{raw:,.0f}"
            return value if role == Qt.ToolTipRole else value[:500]
        if role == Qt.TextAlignmentRole:
            raw = self.frame.iloc[int(self.positions[index.row()]), index.column()]
            return int(Qt.AlignVCenter | (Qt.AlignRight if isinstance(raw, Real) else Qt.AlignLeft))
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self.frame.columns[section])
        return str(int(self.positions[section]) + 1)


class StatusDelegate(QStyledItemDelegate):
    COLORS = {"严重": ("#fcebea", "#b64242"), "警告": ("#fff1d9", "#9f6918"),
              "提示": ("#eaf0fb", "#466a9e"), "成功": ("#e3f3ec", "#26755b"), "失败": ("#fcebea", "#b64242")}

    def paint(self, painter, option, index):
        text = str(index.data() or "")
        if text not in self.COLORS:
            return super().paint(painter, option, index)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        background = option.palette.highlight() if option.state & QStyle.State_Selected else option.palette.alternateBase() if index.row() % 2 else option.palette.base()
        painter.fillRect(option.rect, background)
        rect = option.rect.adjusted(10, 7, -10, -7)
        rect.setWidth(min(62, rect.width()))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.COLORS[text][0]))
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(QColor(self.COLORS[text][1]))
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()


class DataTable(QTableView):
    def __init__(self, frame=None, parent=None, *, formatted=False, status_columns=(), empty_text="暂无数据\n打开 Excel 或 CSV 后在这里查看内容"):
        super().__init__(parent)
        self.data_model = DataFrameModel(frame, self)
        self.data_model.format_numbers = formatted
        self.status_columns = status_columns
        self.badges = StatusDelegate(self)
        self.setModel(self.data_model)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setEditTriggers(QTableView.NoEditTriggers)
        self.verticalHeader().setDefaultSectionSize(38)
        self.setShowGrid(False)
        self.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setDefaultSectionSize(150)
        self.horizontalHeader().setStretchLastSection(True)
        self.setWordWrap(False)
        self.setMinimumHeight(100)
        self.empty = QLabel(empty_text, self.viewport())
        self.empty.setObjectName("tableEmpty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.data_model.modelReset.connect(self.update_empty)
        self.update_empty()

    def set_frame(self, frame, positions=None):
        self.data_model.set_frame(frame, positions)
        for i, column in enumerate(frame.columns):
            self.setItemDelegateForColumn(i, self.badges if column in self.status_columns else None)

    def update_empty(self):
        self.empty.setVisible(self.data_model.rowCount() == 0)
        self.empty.setGeometry(self.viewport().rect().adjusted(16, 8, -16, -8))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_empty()
