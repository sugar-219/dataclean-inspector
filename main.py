"""数据清洗与质量检测工具软件 V1.0 的 Windows 桌面入口。"""
import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="数据清洗与质量检测工具软件 V1.0")
    parser.add_argument("--open", help="启动后打开指定数据文件")
    parser.add_argument("--smoke-test", action="store_true", help="离屏启动并自动退出，用于环境验证")
    args = parser.parse_args()
    if args.smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer, QTranslator, QLibraryInfo, QLocale
    from PySide6.QtWidgets import QApplication, QMessageBox
    from app import APP_NAME
    from app.utils.config import data_directory
    os.environ.setdefault("MPLCONFIGDIR", str(data_directory() / ".matplotlib"))
    from app.utils.logger import setup_logger
    from app.utils.helpers import resource_path
    from app.ui.main_window import MainWindow
    logger = setup_logger()
    app = QApplication(sys.argv[:1])
    from app.ui.fonts import setup_fonts
    setup_fonts(app)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("DataCleanInspector")
    QLocale.setDefault(QLocale(QLocale.Chinese, QLocale.China))
    translator = QTranslator(app)
    translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.TranslationsPath))
    app.installTranslator(translator)
    app.setStyle("Fusion")
    app.setStyleSheet(resource_path("resources/style.qss").read_text(encoding="utf-8"))

    def exception_handler(kind, value, trace):
        logger.error("未处理的界面异常", exc_info=(kind, value, trace))
        QMessageBox.warning(None, "操作未完成", "发生异常，程序已记录详情。请重试当前操作。\n" + str(value))
    sys.excepthook = exception_handler
    window = MainWindow()
    window.show()
    logger.info("软件启动")
    if args.open:
        QTimer.singleShot(0, lambda: window.open_path(args.open))
    if args.smoke_test:
        def finish():
            if window.busy:
                QTimer.singleShot(100, finish)
            else:
                app.exit(1 if window.last_error else 0)
        QTimer.singleShot(1200, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
