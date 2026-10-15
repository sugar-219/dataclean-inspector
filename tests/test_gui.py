"""真实 Qt 控件及后台任务集成验证，无需显示器和 pytest-qt。"""
from pathlib import Path
import time
import pandas as pd
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog, QDialog
from PySide6.QtTest import QTest
from app.ui.main_window import MainWindow
from app.ui.fonts import setup_fonts
from app.ui.widgets.data_table import DataFrameModel, DataTable
from app.core.data_query import search_positions
from app.utils.config import ConfigStore
from app.utils.helpers import resource_path


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    setup_fonts(app)
    app.setStyle("Fusion")
    app.setStyleSheet(resource_path("resources/style.qss").read_text(encoding="utf-8"))
    yield app


@pytest.fixture
def window(qt_app, tmp_path, monkeypatch):
    win = MainWindow(ConfigStore(tmp_path / "config.json"))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)
    win.show()
    qt_app.processEvents()
    yield win
    wait_ready(win)
    win.manager.dirty = False
    win.close()


def wait_ready(win, timeout=30):
    end = time.monotonic() + timeout
    while win.busy and time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(.005)
    QApplication.processEvents()
    assert not win.busy, "后台任务超时"


def test_model_is_virtual_and_search_sort(qt_app):
    frame = pd.DataFrame({"a": range(100000), "b": ["文字"] * 100000})
    model = DataFrameModel(frame)
    assert model.rowCount() == 100000
    assert model.data(model.index(99999, 0)) == "99999"
    assert search_positions(frame, "99999", 0, True).tolist() == [99999]
    assert search_positions(frame, "", 0, False)[0] == 99999


def test_full_window_workflow(window, tmp_path):
    window.open_path(str(resource_path("samples/student_data.xlsx")))
    wait_ready(window)
    assert not window.last_error
    assert len(window.manager.frame) == 123
    assert window.preview.table.model().rowCount() == 123
    assert window.manager.result.metrics["duplicates"] == 3
    before = window.manager.frame.copy()
    window.navigation.setCurrentRow(3)
    window.cleaning.operation.setCurrentText("删除重复行")
    window.cleaning.submit()
    wait_ready(window)
    assert len(window.manager.frame) == 120
    assert len(window.manager.undo) == 1
    window.undo()
    wait_ready(window)
    pd.testing.assert_frame_equal(window.manager.frame, before)
    window.search("模拟学员", -1, True)
    wait_ready(window)
    assert len(window.preview.positions) < 123
    for index in range(8):
        window.navigation.setCurrentRow(index)
        QApplication.processEvents()
        assert window.stack.currentIndex() == index
    for kind in range(4):
        window.analysis.kind.setCurrentIndex(kind)
        window.analysis.canvas.draw()
        assert "失败" not in window.analysis.message.text()
        assert window.analysis.figure.axes
    path = tmp_path / "export.xlsx"
    window.export_to(path)
    wait_ready(window)
    assert path.is_file()
    assert not window.manager.dirty
    assert "评分组成" in window.report.browser.toPlainText()


def test_failed_clean_leaves_state_and_undo(window):
    window.load_path(str(resource_path("samples/student_data.xlsx")))
    wait_ready(window)
    before = window.manager.frame.copy()
    window.apply_clean("数据类型转换", ["年龄"], {"target": "整数"})
    wait_ready(window)
    assert "不能转换" in window.last_error
    pd.testing.assert_frame_equal(window.manager.frame, before)
    assert len(window.manager.undo) == 0
    assert window.manager.records[-1].success is False
    assert window.centralWidget().isEnabled()


def test_multi_sheet_dialog(window, monkeypatch):
    chosen = []
    def select(*args):
        chosen.extend(args[3])
        return "客户数据", True
    monkeypatch.setattr(QInputDialog, "getItem", select)
    window.open_path(str(resource_path("samples/customer_data.xlsx")))
    wait_ready(window)
    assert chosen == ["客户数据", "数据说明"]
    assert len(window.manager.frame) == 123


def test_overwrite_cancel_keeps_source(window, monkeypatch, tmp_path):
    target = tmp_path / "原文件.csv"
    target.write_text("不能覆盖", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), "CSV (*.csv)"))
    monkeypatch.setattr(window, "confirm", lambda *args: False)
    assert window.save_target("导出", ".csv", "CSV (*.csv)", "数据.csv") is None
    assert target.read_text(encoding="utf-8") == "不能覆盖"


def test_settings_update_comparison(window):
    window.load_path(str(resource_path("samples/student_data.xlsx")))
    wait_ready(window)
    values = dict(window.config.values, missing_threshold=.6, iqr_factor=2.)
    window.save_settings(values)
    wait_ready(window)
    assert window.manager.settings["missing_threshold"] == .6
    assert ConfigStore(window.config.path).values["iqr_factor"] == 2.
    assert window.manager.baseline.score == window.manager.result.score


def test_issue_details_has_actual_rows(window, monkeypatch):
    window.load_path(str(resource_path("samples/student_data.xlsx")))
    wait_ready(window)
    window.quality.category.setCurrentText("重复值")
    window.quality.table.selectRow(0)
    counts = []
    def inspect(dialog):
        counts.extend(table.model().rowCount() for table in dialog.findChildren(DataTable))
        return 0
    monkeypatch.setattr(QDialog, "exec", inspect)
    window.quality.show_details()
    assert counts == [3]


@pytest.mark.parametrize("filename,sheet", [("student_data.xlsx", None), ("sales_data.csv", None), ("customer_data.xlsx", "客户数据")])
def test_each_sample_navigation_and_cleaning(window, filename, sheet):
    window.load_path(str(resource_path("samples/" + filename)), sheet)
    wait_ready(window)
    assert not window.last_error
    assert window.manager.frame.shape == (123, 8)
    for index in range(8):
        window.navigation.setCurrentRow(index)
        QApplication.processEvents()
        assert window.stack.currentWidget().isVisible()
    score = window.manager.result.score["score"]
    window.cleaning.operation.setCurrentText("删除重复行")
    window.cleaning.submit()
    wait_ready(window)
    assert len(window.manager.frame) == 120
    assert window.manager.result.score["score"] > score
    window.undo()
    wait_ready(window)
    assert len(window.manager.frame) == 123
    assert window.manager.result.score["score"] == score


def test_empty_state_buttons_and_pages(window, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QPushButton, QLabel, QLineEdit
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("", ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(tmp_path / "空操作记录.csv"), "CSV (*.csv)"))
    monkeypatch.setattr(window, "confirm", lambda *args: True)
    clicked = []
    for page_index in range(8):
        window.navigation.setCurrentRow(page_index)
        QApplication.processEvents()
        for widget in window.stack.currentWidget().findChildren(QPushButton):
            if widget.isVisible() and widget.isEnabled():
                QTest.mouseClick(widget, Qt.LeftButton)
                wait_ready(window)
                clicked.append(widget.text())
        for label in window.stack.currentWidget().findChildren(QLabel):
            assert not any(word in label.text().lower() for word in ["todo", "placeholder", "mock", "debug"])
        for edit in window.stack.currentWidget().findChildren(QLineEdit):
            assert not any(word in edit.placeholderText().lower() for word in ["todo", "placeholder", "mock", "debug"])
    window.open_dialog()
    window.export_dialog()
    window.undo()
    assert window.manager.original is None
    assert not window.last_error
    assert not window.busy
    assert "执行清洗" in clicked
    assert "开始质量检测" in clicked
    assert "导出 HTML 检测报告" in clicked
    assert (tmp_path / "空操作记录.csv").is_file()


@pytest.mark.parametrize("filename,content", [("空.csv", b""), ("损坏.xlsx", b"broken"), ("不支持.txt", b"a"),
    ("错误编码.csv", b"name\n\xff\xff"), ("只有表头.csv", "名称,年龄\n".encode("utf-8")),
    ("错列.csv", "甲,乙\n1,2,3\n4,5,6\n".encode("utf-8")), ("不存在.csv", None)])
def test_bad_files_keep_previous_data_and_ui_alive(window, tmp_path, filename, content):
    window.load_path(str(resource_path("samples/sales_data.csv")))
    wait_ready(window)
    before = window.manager.frame.copy(deep=True)
    path = tmp_path / filename
    if content is not None:
        path.write_bytes(content)
    window.open_path(str(path))
    wait_ready(window)
    assert window.last_error
    assert window.manager.records[-1].success is False
    pd.testing.assert_frame_equal(window.manager.frame, before)
    assert window.centralWidget().isEnabled()
    for index in range(8):
        window.navigation.setCurrentRow(index)
        QApplication.processEvents()
        assert window.stack.currentIndex() == index


@pytest.mark.parametrize("size", [(1100, 700), (1280, 800), (1600, 1000)])
def test_responsive_pages_and_cleaning_controls(window, size):
    from PySide6.QtWidgets import QScrollArea
    window.resize(*size)
    for index in range(8):
        window.navigation.setCurrentRow(index)
        QApplication.processEvents()
        scroll = window.stack.currentWidget()
        assert window.size().toTuple() == size
        assert scroll.horizontalScrollBar().maximum() == 0
    window.navigation.setCurrentRow(3)
    for operation in ["缺失值填充", "文本批量替换", "删除指定行"]:
        window.cleaning.operation.setCurrentText(operation)
        QApplication.processEvents()
        scroll = window.cleaning.findChild(QScrollArea)
        scroll.ensureWidgetVisible(window.cleaning.apply_button)
        QApplication.processEvents()
        button = window.cleaning.apply_button
        assert scroll.viewport().rect().contains(button.mapTo(scroll.viewport(), button.rect().center()))


def test_stat_formatting_preserves_original_values(qt_app):
    frame = pd.DataFrame({"数值": [12345.678912], "缺失率": [.123456]})
    raw = DataTable(frame)
    stats = DataTable(frame, formatted=True)
    raw_index = raw.model().index(0, 0)
    index = stats.model().index(0, 0)
    assert raw.model().data(raw_index) == "12345.678912"
    assert stats.model().data(index) == "12,345.6789"
    assert stats.model().data(index, Qt.ToolTipRole) == "12345.678912"
    assert stats.model().data(stats.model().index(0, 1)) == "12.3%"
    assert frame.iloc[0, 0] == 12345.678912


def test_loading_error_notice_and_dismiss(window, tmp_path):
    bad = tmp_path / "损坏.xlsx"
    bad.write_bytes(b"broken")
    window.load_path(str(bad))
    assert window.notice.isVisible()
    assert window.notice.property("level") == "处理中"
    assert not window.notice.dismiss.isVisible()
    wait_ready(window)
    assert window.notice.isVisible()
    assert window.notice.property("level") == "严重"
    assert window.last_error in window.notice.label.text()
    QTest.mouseClick(window.notice.dismiss, Qt.LeftButton)
    assert not window.notice.isVisible()
    assert window.manager.original is None
    window.load_path(str(resource_path("samples/sales_data.csv")))
    wait_ready(window)
    assert not window.last_error
    assert not window.notice.isVisible()


def test_empty_states_and_score_refresh(window):
    from PySide6.QtWidgets import QPushButton
    assert window.home.score.dial.score is None
    assert not window.home.inspect.isEnabled()
    assert window.home.recent_empty.isVisible()
    assert not any("体验" in b.text() or "测试" in b.text() for b in window.findChildren(QPushButton))
    window.navigation.setCurrentRow(1)
    QApplication.processEvents()
    assert window.preview.table.empty.isVisible()
    window.load_path(str(resource_path("samples/sales_data.csv")))
    wait_ready(window)
    before = window.manager.result.score["score"]
    assert window.home.score.dial.score == window.quality.score.dial.score == before
    window.apply_clean("删除重复行", [], {})
    wait_ready(window)
    after = window.manager.result.score["score"]
    assert after > before
    assert window.home.score.dial.score == window.quality.score.dial.score == after
    assert f"{after - before:+.2f}" in window.cleaning.delta.text()
    window.undo()
    wait_ready(window)
    assert window.home.score.dial.score == window.quality.score.dial.score == before


def test_cleaning_fields_and_parameter_visibility(window):
    from app.core.cleaner import OPERATIONS

    window.navigation.setCurrentRow(3)
    page = window.cleaning
    whole_table = {"删除重复行", "删除空行", "删除高缺失字段", "删除指定行"}
    for operation in OPERATIONS:
        page.operation.setCurrentText(operation)
        QApplication.processEvents()
        assert page.columns.isEnabled() == (operation not in whole_table)
        assert page.select_all.isEnabled() == (operation not in whole_table)

    page.operation.setCurrentText("缺失值填充")
    page.method.setCurrentText("固定值")
    assert not page.value.isHidden()
    for method in ["均值", "中位数", "众数", "前向填充", "后向填充"]:
        page.method.setCurrentText(method)
        assert page.value.isHidden()
        assert not page.method.isHidden()
    page.operation.setCurrentText("文本批量替换")
    assert not page.old.isHidden() and not page.new.isHidden()
    assert page.method.isHidden()

