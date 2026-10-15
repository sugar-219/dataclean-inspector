"""可重跑的 GUI 截图和十万行混合数据端到端性能验证。"""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))
os.environ.setdefault("DATACLEAN_HOME", str(ROOT / "verification"))
import numpy as np
import pandas as pd
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app.ui.main_window import MainWindow
from app.ui.fonts import setup_fonts
from app.utils.helpers import resource_path
from app.utils.logger import setup_logger
from app.core.file_loader import export_data, load_file
from app.core.report_generator import export_report


def run():
    output = ROOT / "verification"
    shots = ROOT / "docs/screenshots"
    output.mkdir(exist_ok=True)
    shots.mkdir(parents=True, exist_ok=True)
    setup_logger()
    app = QApplication([])
    setup_fonts(app)
    app.setStyle("Fusion")
    app.setStyleSheet(resource_path("resources/style.qss").read_text(encoding="utf-8"))
    window = MainWindow()
    errors = []
    window.show_error = errors.append
    window.show()
    timings = {}
    ticks = []
    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
    timer.start()

    def wait(label):
        start = time.perf_counter()
        while window.busy:
            app.processEvents()
            time.sleep(.005)
            if time.perf_counter() - start > 240:
                raise RuntimeError(label + "超时")
        app.processEvents()
        timings[label] = round(time.perf_counter() - start, 3)
        print(label, timings[label], "秒", flush=True)
        assert not errors, errors

    window.load_path(str(resource_path("samples/student_data.xlsx")))
    wait("示例导入检测统计报告")
    for i, name in enumerate(["01-首页", "02-数据预览", "03-质量检测", "04-数据清洗", "05-数据分析", "06-检测报告", "07-操作记录", "08-设置"]):
        window.navigation.setCurrentRow(i)
        app.processEvents()
        QTest.qWait(50)
        window.grab().save(str(shots / (name + ".png")))
    window.resize(1100, 700)
    window.navigation.setCurrentRow(3)
    app.processEvents()
    window.grab().save(str(shots / "09-最低分辨率.png"))
    window.resize(1280, 800)
    if "--screenshots-only" in sys.argv:
        window.close()
        print("SCREENSHOTS_OK")
        return 0
    rng = np.random.default_rng(42)
    data = {}
    for col in range(15):
        values = rng.normal(100, 20, 100000)
        values[::1000] = np.nan
        values[1::2000] = 99999
        data[f"数值{col + 1}"] = values
    for col in range(10):
        data[f"文本{col + 1}"] = np.where(np.arange(100000) % 1000 == 0, " 有空格 ", np.where(np.arange(100000) % 3 == 0, "分类甲", "分类乙"))
    for col in range(5):
        data[f"日期{col + 1}"] = np.where(np.arange(100000) % 1000 == 0, "无效日期", "2026-01-01")
    large = pd.DataFrame(data)
    large.iloc[-5:] = large.iloc[:5].to_numpy()
    expected_duplicates = int(large.duplicated().sum())
    source = output / "benchmark_100000x30.csv"
    large.to_csv(source, index=False, encoding="utf-8-sig")
    del large, data
    ticks.clear()
    window.load_path(str(source))
    wait("十万行CSV导入检测统计报告")
    intervals = np.diff(ticks)
    timings["导入期间界面计时器响应次数"] = len(ticks)
    timings["导入期间最大响应间隔秒"] = round(float(intervals.max()), 3) if len(intervals) else None
    assert window.manager.frame.shape == (100000, 30)
    assert len(ticks) >= 2
    assert window.preview.table.model().rowCount() == 500
    window.search("无效日期", 0, True)
    wait("十万行搜索排序")
    assert len(window.preview.positions) >= 100
    window.apply_clean("删除重复行", [], {})
    wait("十万行去重重新检测")
    assert len(window.manager.frame) == 100000 - expected_duplicates
    window.undo()
    wait("十万行撤销重新检测")
    assert len(window.manager.frame) == 100000
    for suffix in (".csv", ".xlsx"):
        target = output / ("benchmark_export" + suffix)
        window.export_to(target)
        wait("十万行导出" + suffix)
        start = time.perf_counter()
        restored, _ = load_file(target)
        timings["十万行重读" + suffix] = round(time.perf_counter() - start, 3)
        assert restored.shape == (100000, 30)
    export_report(window.manager, output / "benchmark_report.html")
    timings["最终数据规模"] = list(window.manager.frame.shape)
    timings["错误"] = errors
    (output / "benchmark_results.json").write_text(json.dumps(timings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(timings, ensure_ascii=False, indent=2))
    window.manager.dirty = False
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
