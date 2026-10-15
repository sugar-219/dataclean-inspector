"""本地轮转日志，保存异常栈以便排查。"""
import logging
from logging.handlers import RotatingFileHandler
from app.utils.config import data_directory


def setup_logger():
    logger = logging.getLogger("dataclean")
    if not logger.handlers:
        directory = data_directory() / "logs"
        directory.mkdir(exist_ok=True)
        handler = RotatingFileHandler(directory / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
