"""真实 Qt 页面、缩放和状态截图；输出与日常配置隔离。"""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "verification/ui_check"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from app.ui.fonts import setup_fonts
from app.ui.main_window import MainWindow
from app.utils.config import ConfigStore


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    setup_fonts(app)
    app.setStyle("Fusion")
    app.setStyleSheet((ROOT / "resources/style.qss").read_text(encoding="utf-8"))
    config = ConfigStore(OUTPUT / "config.json")
    config.values["recent_files"] = []
    window = MainWindow(config)
    window.show()
    evidence = {"pages": [], "states": []}

    def capture(name):
        app.processEvents()
        assert window.grab().save(str(OUTPUT / (name + ".png")))

    def wait():
        deadline = time.monotonic() + 30
        while window.busy:
            app.processEvents()
            time.sleep(.005)
            assert time.monotonic() < deadline, "任务超时"
        app.processEvents()

    capture("empty-home")
    for index in [1, 2, 4]:
        window.navigation.setCurrentRow(index)
        capture(f"empty-page-{index}")
    window.navigation.setCurrentRow(0)
    window.load_path(str(ROOT / "samples/student_data.xlsx"))
    assert window.notice.property("level") == "处理中"
    # 不派发完成信号，在真实导入任务期间绘制加载状态。
    assert window.grab().save(str(OUTPUT / "loading.png"))
    wait()
    assert not window.last_error
    evidence["states"].extend(["empty", "loading"])
    for width, height in [(1100, 700), (1280, 800), (1600, 1000)]:
        window.resize(width, height)
        for index in range(8):
            window.navigation.setCurrentRow(index)
            capture(f"{width}x{height}-page-{index}")
            scroll = window.stack.currentWidget()
            assert window.size().toTuple() == (width, height)
            assert scroll.horizontalScrollBar().maximum() == 0
            evidence["pages"].append({"size": [width, height], "page": index,
                                      "vertical_scroll": scroll.verticalScrollBar().maximum()})
    window.resize(1100, 700)
    window.navigation.setCurrentRow(3)
    window.cleaning.operation.setCurrentText("文本批量替换")
    capture("small-cleaning-replace")
    window.apply_clean("数据类型转换", ["年龄"], {"target": "整数"})
    wait()
    assert window.last_error and window.notice.isVisible()
    capture("error")
    window.notice.dismiss.click()
    assert not window.notice.isVisible()
    evidence["states"].extend(["error", "dismiss"])
    window.manager.dirty = False
    window.close()
    (OUTPUT / "results.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print("UI_CHECK_OK: 24 page/size combinations, empty/loading/error/dismiss states")


if __name__ == "__main__":
    main()
