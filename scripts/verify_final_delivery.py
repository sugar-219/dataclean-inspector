"""V1.0 原生 Qt 核心流程验收，独立进程确认设置重启持久化。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "verification/final_v1.0"
sys.path.insert(0, str(ROOT))
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["DATACLEAN_HOME"] = str(OUTPUT / "profile")
os.environ["MPLCONFIGDIR"] = str(OUTPUT / "matplotlib")

import pandas as pd
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QLineEdit, QComboBox
from app.ui.main_window import MainWindow
from app.ui.fonts import setup_fonts
from app.utils.logger import setup_logger
from app.core.file_loader import load_file


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    setup_logger()
    app = QApplication([])
    setup_fonts(app)
    app.setStyle("Fusion")
    app.setStyleSheet((ROOT / "resources/style.qss").read_text(encoding="utf-8"))
    win = MainWindow()
    win.show()
    app.processEvents()
    if "--restart-check" in sys.argv:
        assert win.settings.threshold.value() == 40
        assert win.settings.iqr.value() == 2
        assert win.settings.undo.value() == 10
        assert win.settings.date.currentText() == "YYYY/MM/DD"
        assert not win.settings.recent.isChecked()
        win.navigation.setCurrentRow(7)
        app.processEvents()
        win.grab().save(str(OUTPUT / "settings-restarted.png"))
        win.close()
        print("SETTINGS_RESTART_OK")
        return

    def wait():
        end = time.monotonic() + 60
        while win.busy:
            app.processEvents()
            time.sleep(.005)
            assert time.monotonic() < end, "后台任务超时"
        app.processEvents()
        assert not win.last_error, win.last_error

    def shot(name, page):
        win.navigation.setCurrentRow(page)
        app.processEvents()
        assert win.grab().save(str(OUTPUT / (name + ".png")))

    # 重跑时先恢复验收基准参数，使用独立配置，不改变日常配置。
    win.save_settings(dict(missing_threshold=.3, iqr_factor=1.5, undo_limit=20,
                           date_format="YYYY-MM-DD", show_recent=True))
    wait()
    shot("01-home", 0)
    win.open_path(str(ROOT / "samples/student_data.xlsx"))
    wait()
    assert win.manager.frame.shape == (123, 8)
    shot("02-preview", 1)
    assert win.preview.table.model().rowCount() == 123
    assert win.preview.fields.model().rowCount() == 8
    win.detect()
    wait()
    before = win.manager.result
    assert before.metrics["missing"] == 73 and before.metrics["duplicates"] == 3
    assert before.metrics["outliers"] == 9 and before.score["score"] == 96.51
    expected = {"缺失值", "重复行", "数值异常值", "数据类型异常", "日期格式异常"}
    assert expected <= {issue.kind for issue in before.issues}
    for category in ["缺失值", "重复值", "异常值", "类型异常", "格式异常"]:
        win.quality.category.setCurrentText(category)
        assert win.quality.table.model().rowCount() > 0
        shot("issue-" + category, 2)
    win.quality.category.setCurrentText("全部")
    shot("03-quality", 2)

    operations = [("删除重复行", [], {}), ("文本去除前后空格", ["名称"], {}),
                  ("缺失值填充", ["备注"], {"value": "未填写"})]
    for operation, columns, params in operations:
        old = win.manager.frame.copy(deep=True)
        win.cleaning.operation.setCurrentText(operation)
        win.cleaning.columns.clearSelection()
        for i in range(win.cleaning.columns.count()):
            item = win.cleaning.columns.item(i)
            item.setSelected(item.text() in columns)
        if params:
            win.cleaning.method.setCurrentText("固定值")
            win.cleaning.value.setText(params["value"])
        win.cleaning.submit()
        wait()
        assert not win.manager.frame.equals(old), operation
    cleaned = win.manager.frame.copy(deep=True)
    win.undo()
    wait()
    pd.testing.assert_frame_equal(win.manager.frame, old)
    win.cleaning.submit()
    wait()
    pd.testing.assert_frame_equal(win.manager.frame, cleaned)
    assert win.home.score.dial.score == win.manager.result.score["score"] > before.score["score"]
    score_after_cleaning = win.home.score.dial.score
    assert win.cleaning.comparison.model().rowCount() == 6
    shot("04-cleaning-comparison", 3)
    for i in range(4):
        win.analysis.kind.setCurrentIndex(i)
        win.analysis.canvas.draw()
        assert "失败" not in win.analysis.message.text()
        assert win.analysis.figure.axes
        shot("chart-" + str(i), 4)

    report_path = OUTPUT / "质量检测报告.html"
    original_target = win.save_target
    try:
        # 仅文件保存路径受控，报告生成和写入均走正式页面信号与后台任务。
        win.save_target = lambda *args: report_path
        win.report.export_requested.emit()
        wait()
    finally:
        win.save_target = original_target
    html = report_path.read_text(encoding="utf-8")
    assert "评分组成" in html and "<html" in html.lower()
    shot("05-report", 5)
    for suffix in ["xlsx", "csv"]:
        target = OUTPUT / ("清洗结果." + suffix)
        win.export_to(target)
        wait()
        restored, _ = load_file(target)
        assert restored.shape == cleaned.shape
        assert restored["备注"].tolist() == cleaned["备注"].tolist()
        assert restored["名称"].tolist() == cleaned["名称"].fillna("").tolist()
    shot("06-history", 6)
    assert any(r.operation == "撤销" for r in win.manager.records)
    text_checks = 0
    banned = ["todo", "test", "demo", "lorem ipsum", "debug", "placeholder", "开发测试", "临时功能"]
    for page in range(8):
        win.navigation.setCurrentRow(page)
        app.processEvents()
        for widget in win.stack.currentWidget().findChildren(QWidget):
            if not widget.isVisible() or not isinstance(widget, (QLabel, QPushButton, QLineEdit, QComboBox)):
                continue
            values = [widget.itemText(i) for i in range(widget.count())] if isinstance(widget, QComboBox) else [widget.placeholderText()] if isinstance(widget, QLineEdit) else [widget.text()]
            for value in values:
                assert not any(word in value.lower() for word in banned), value
                text_checks += 1
    win.settings.threshold.setValue(40)
    win.settings.iqr.setValue(2)
    win.settings.undo.setValue(10)
    win.settings.date.setCurrentText("YYYY/MM/DD")
    win.settings.recent.setChecked(False)
    win.settings.submit()
    wait()
    shot("07-settings", 7)
    win.close()
    child = subprocess.run([sys.executable, __file__, "--restart-check"], capture_output=True, timeout=30)
    assert child.returncode == 0, child.stderr.decode("utf-8", errors="replace")
    result = {"platform": app.platformName(), "sample_shape": [123, 8], "before_metrics": before.metrics,
              "score_before": before.score["score"], "score_after_cleaning": float(score_after_cleaning),
              "operations": [x[0] for x in operations], "undo_verified": True,
              "charts": 4, "html": True, "export_shapes": [120, 8], "visible_texts_checked": text_checks,
              "settings_restart": child.stdout.decode().strip(), "status": "PASS"}
    (OUTPUT / "workflow.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
