"""轻量线条导航图标，由 Qt 绘制，无额外图标字体或依赖。"""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QIcon
from app.ui.widgets import icon_resources  # 注册内嵌箭头，不依赖启动目录。


def navigation_icon(index):
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#aec3cc"), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    if index == 0:
        for x in (4, 14):
            for y in (4, 14):
                painter.drawRoundedRect(QRectF(x, y, 6, 6), 1, 1)
    elif index == 1:
        painter.drawRoundedRect(QRectF(3, 4, 18, 16), 2, 2)
        painter.drawLine(3, 10, 21, 10)
        painter.drawLine(9, 10, 9, 20)
        painter.drawLine(3, 15, 21, 15)
    elif index == 2:
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawLine(7, 12, 10, 15)
        painter.drawLine(10, 15, 17, 8)
    elif index == 3:
        painter.drawLine(4, 5, 20, 5)
        painter.drawLine(4, 5, 10, 13)
        painter.drawLine(20, 5, 14, 13)
        painter.drawLine(10, 13, 10, 20)
        painter.drawLine(14, 13, 14, 18)
        painter.drawLine(10, 20, 14, 18)
    elif index == 4:
        painter.drawLine(4, 20, 21, 20)
        for x, y in ((7, 12), (12, 7), (17, 3)):
            painter.drawLine(x, y, x, 17)
    elif index == 5:
        painter.drawRoundedRect(QRectF(5, 3, 14, 18), 2, 2)
        for y in (8, 12, 16):
            painter.drawLine(8, y, 16, y)
    elif index == 6:
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawLine(12, 7, 12, 12)
        painter.drawLine(12, 12, 16, 14)
    else:
        for y, x in ((6, 9), (12, 16), (18, 7)):
            painter.drawLine(3, y, 21, y)
            painter.setBrush(QColor("#172f40"))
            painter.drawEllipse(QPointF(x, y), 2.5, 2.5)
    painter.end()
    return QIcon(pixmap)
