"""在干净的 Windows DLL 搜索路径下构建，避免收集其他工具链的同名库。"""
from pathlib import Path
import os
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".matplotlib"))
    windows = Path(os.environ.get("WINDIR", "C:/Windows"))
    # MSYS / Anaconda PATH 中的 ICU 可能与 Qt 所需的 Windows ICU 同名但 ABI 不兼容。
    os.environ["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), sys.base_prefix,
                                        str(windows / "System32"), str(windows)])
    from PyInstaller.__main__ import run
    run(["--noconfirm", "--clean", "--windowed", "--onedir", "--name", "数据清洗与质量检测工具",
         "--add-data", "resources;resources", "--add-data", "samples;samples", "--hidden-import", "xlrd",
         "--hidden-import", "openpyxl", "--exclude-module", "PySide6.QtWebEngineCore",
         "--exclude-module", "PySide6.QtWebEngineWidgets", "--exclude-module", "pytest",
         "--exclude-module", "_pytest", "main.py"])


if __name__ == "__main__":
    main()
