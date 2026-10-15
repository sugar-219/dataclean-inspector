"""在离屏 Qt 环境显式加载 Windows 系统字体，不随软件分发字体文件。"""
from pathlib import Path
import os
from PySide6.QtGui import QFontDatabase, QFont


def setup_fonts(app):
    windows_directory = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if not QFontDatabase.families() and windows_directory:
        directory = Path(windows_directory) / "Fonts"
        for filename in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf"):
            path = directory / filename
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
    app.setFont(QFont("Microsoft YaHei UI", 10))
