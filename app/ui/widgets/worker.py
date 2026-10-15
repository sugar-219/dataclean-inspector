"""单个后台任务；仅通过信号回到主线程更新界面。"""
import traceback
from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    succeeded = Signal(object)
    failed = Signal(str, str)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            value = self.function()
            self.succeeded.emit(value)
        except Exception as exc:
            message = str(exc)
            if isinstance(exc, PermissionError):
                message = "文件没有访问权限或正在被其他程序占用，请关闭占用文件的程序并检查目录权限。"
            elif isinstance(exc, OSError):
                message = "文件访问失败，请检查路径、磁盘空间及目录是否可用。"
            elif isinstance(exc, MemoryError):
                message = "可用内存不足，请减少撤销历史数量或缩小数据范围后重试。"
            self.failed.emit(message, traceback.format_exc())
