"""JSON 设置和最近文件；开发目录可写时使用项目目录，打包后使用用户目录。"""
from pathlib import Path
import json
import os
import sys
from app.core.file_loader import atomic_write
from app.core.cleaner import DATE_FORMATS

DEFAULTS = {"missing_threshold": .3, "iqr_factor": 1.5, "undo_limit": 20,
            "date_format": "YYYY-MM-DD", "show_recent": True, "recent_files": []}


def data_directory():
    override = os.environ.get("DATACLEAN_HOME")
    if override:
        root = Path(override)
    elif getattr(sys, "frozen", False):
        root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DataCleanInspector"
    else:
        root = Path(__file__).resolve().parents[2]
        if not os.access(root, os.W_OK):
            root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DataCleanInspector"
    root.mkdir(parents=True, exist_ok=True)
    return root


class ConfigStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_directory() / "config.json"
        self.values = dict(DEFAULTS, recent_files=[])
        self.warning = ""
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                self.values.update(self.validate(saved))
            except (ValueError, TypeError, OverflowError, OSError):
                self.warning = "配置文件无法读取，已使用默认设置；保存设置后可修复。"

    @staticmethod
    def validate(values):
        if not isinstance(values, dict):
            raise ValueError("配置内容无效。")
        config = {key: values.get(key, default) for key, default in DEFAULTS.items()}
        if not .01 <= float(config["missing_threshold"]) <= 1:
            raise ValueError("高缺失率阈值应为 1% 至 100%。")
        if not .1 <= float(config["iqr_factor"]) <= 10:
            raise ValueError("IQR 系数应为 0.1 至 10。")
        if not 1 <= int(config["undo_limit"]) <= 20:
            raise ValueError("撤销数量应为 1 至 20。")
        if not isinstance(config["show_recent"], bool):
            raise ValueError("最近文件开关必须为布尔值。")
        if config["date_format"] not in DATE_FORMATS:
            raise ValueError("日期格式无效。")
        if not isinstance(config["recent_files"], list) or not all(isinstance(p, str) for p in config["recent_files"]):
            raise ValueError("最近文件配置无效。")
        config.update(missing_threshold=float(config["missing_threshold"]), iqr_factor=float(config["iqr_factor"]), undo_limit=int(config["undo_limit"]))
        return config

    def save(self, changes):
        values = self.validate(dict(self.values, **changes))
        atomic_write(self.path, lambda path: path.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8"))
        self.values = values

    def add_recent(self, path):
        recent = [path] + [p for p in self.values["recent_files"] if p != path]
        self.save({"recent_files": recent[:8]})
