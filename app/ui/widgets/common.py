from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont


def button(text, callback=None, primary=False):
    widget = QPushButton(text)
    widget.setCursor(Qt.PointingHandCursor)
    if primary:
        widget.setObjectName("primary")
    if callback:
        widget.clicked.connect(callback)
    return widget


def muted(text):
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


class Page(QWidget):
    def __init__(self, title, subtitle):
        super().__init__()
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(14)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        heading.setWordWrap(True)
        self.layout.addWidget(heading)
        self.layout.addWidget(muted(subtitle))


class StatCard(QFrame):
    def __init__(self, title, color=False):
        super().__init__()
        self.setObjectName("scoreCard" if color else "card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.addWidget(muted(title))
        self.value = QLabel("—")
        self.value.setObjectName("statValue")
        layout.addWidget(self.value)
        self.detail = muted("")
        self.detail.hide()
        layout.addWidget(self.detail)

    def set_value(self, value):
        self.value.setText(f"{value:,}" if isinstance(value, int) else str(value))

    def set_detail(self, text):
        self.detail.setText(text)
        self.detail.setVisible(bool(text))


def stat_row(titles):
    layout = QHBoxLayout()
    cards = []
    for title in titles:
        card = StatCard(title)
        cards.append(card)
        layout.addWidget(card)
    return layout, cards


def section_title(text):
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


class ScoreDial(QWidget):
    """仅绘制当前得分，不包含评分计算或动画。"""
    def __init__(self):
        super().__init__()
        self.score = None
        self.setFixedSize(118, 118)
        self.setAccessibleName("数据质量评分")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(8, 8, 102, 102)
        painter.setPen(QPen(QColor("#dfebe8"), 7))
        painter.drawArc(rect, 0, 360 * 16)
        if self.score is not None:
            color = "#148575" if self.score >= 80 else "#b67a21" if self.score >= 60 else "#c15353"
            painter.setPen(QPen(QColor(color), 7, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(rect, 90 * 16, -int(self.score * 3.6 * 16))
        painter.setPen(QColor("#173c36"))
        painter.setFont(QFont("Microsoft YaHei UI", 23, QFont.Bold))
        painter.drawText(QRectF(0, 30, 118, 43), Qt.AlignCenter, "—" if self.score is None else f"{self.score:.1f}")
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        painter.setPen(QColor("#738a85"))
        painter.drawText(QRectF(0, 71, 118, 22), Qt.AlignCenter, "满分 100")


class ScoreCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("scoreCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.addWidget(section_title("数据质量评分"))
        row = QHBoxLayout()
        self.dial = ScoreDial()
        row.addWidget(self.dial)
        text = QVBoxLayout()
        self.rating = QLabel("等待检测")
        self.rating.setObjectName("rating")
        self.rating.setProperty("level", "提示")
        text.addWidget(self.rating, 0, Qt.AlignLeft)
        self.caption = muted("导入后自动评估")
        text.addWidget(self.caption)
        text.addStretch()
        row.addLayout(text, 1)
        layout.addLayout(row)
        self.setMinimumWidth(285)

    def set_score(self, score):
        self.dial.score = score["score"]
        self.dial.update()
        self.dial.setAccessibleDescription(f"{score['score']:.1f} 分，{score['rating']}")
        self.rating.setText(score["rating"])
        self.rating.setProperty("level", "成功" if score["score"] >= 80 else "警告" if score["score"] >= 60 else "严重")
        self.rating.style().unpolish(self.rating)
        self.rating.style().polish(self.rating)
        self.caption.setText("结合具体问题判断\n评分仅供整体参考")


class NoticeBar(QFrame):
    """持续可见、可关闭的任务反馈，避免错误提示阻断查看数据。"""
    def __init__(self):
        super().__init__()
        self.setObjectName("noticeBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 16, 10)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.PlainText)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.label, 1)
        self.dismiss = button("关闭提示", self.hide)
        self.dismiss.setObjectName("noticeDismiss")
        layout.addWidget(self.dismiss)
        self.hide()

    def show_message(self, text, level="提示"):
        self.label.setText(text)
        self.setProperty("level", level)
        self.style().unpolish(self)
        self.style().polish(self)
        self.dismiss.setVisible(level != "处理中")
        self.show()
