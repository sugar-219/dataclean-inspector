"""清洗预览的值、原始位置、样例上限及候选提交验证。"""
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from app.core.cleaning_preview import preview_cleaning, PREVIEW_LIMIT
from app.core.data_manager import DataManager


@pytest.mark.parametrize("operation,columns,params", [
    ("删除重复行", [], {}),
    ("删除空行", [], {}),
    ("缺失值填充", ["数量"], {"method": "固定值", "value": "9"}),
    ("删除高缺失字段", [], {"threshold": .5}),
    ("文本去除前后空格", ["姓名"], {}),
    ("大小写转换", ["姓名"], {"case": "全部小写"}),
    ("文本批量替换", ["姓名"], {"old": "Alice", "new": "甲"}),
    ("数据类型转换", ["数量"], {"target": "整数"}),
    ("日期格式统一", ["日期"], {"date_format": "YYYY-MM-DD"}),
    ("删除指定行", [], {"rows": "2,4"}),
    ("删除指定列", ["数量"], {}),
    ("字段重命名", ["姓名"], {"name": "称呼"}),
])
def test_preview_all_operations_is_read_only_and_commits_same_candidate(operation, columns, params):
    frame = pd.DataFrame({"姓名": [" Alice ", " Alice ", "Bob", ""],
                          "数量": ["1", "1", "", ""],
                          "日期": ["2026/1/2", "2026/1/2", "2026-02-03", ""]})
    manager = DataManager()
    manager.load(frame, {"name": "preview.csv"})
    records = len(manager.records)
    change, samples = preview_cleaning(manager.frame, operation, columns, **params)
    assert_frame_equal(manager.frame, frame)
    assert len(manager.undo) == 0 and not manager.dirty
    assert len(manager.records) == records
    assert not samples.empty
    manager.commit_clean(operation, change)
    assert manager.frame is change.frame
    assert len(manager.undo) == 1
    manager.undo_last()
    assert_frame_equal(manager.frame, frame)
    assert not manager.dirty


def test_preview_removed_rows_use_original_positions_and_exact_large_integer():
    frame = pd.DataFrame({"编号": [9007199254740993, 2, 3, 4], "比例": [.1, .2, .3, .4]})
    change, samples = preview_cleaning(frame, "删除指定行", rows="1,4")
    assert change.frame["编号"].tolist() == [2, 3]
    assert samples["数据行号"].tolist() == [1, 1, 4, 4]
    assert samples.iloc[0]["原值"] == "9007199254740993"
    assert set(samples["新值"]) == {"（删除此行）"}


def test_preview_preserves_spaces_and_nullable_missing_and_limits_samples():
    frame = pd.DataFrame({"姓名": [" Alice "] * 150})
    change, samples = preview_cleaning(frame, "文本去除前后空格", ["姓名"])
    assert change.affected == 150
    assert len(samples) == PREVIEW_LIMIT
    assert samples.iloc[0]["原值"] == "' Alice '"
    assert samples.iloc[0]["新值"] == "'Alice'"
    nullable = pd.DataFrame({"数量": pd.Series([pd.NA, 2], dtype="Int64")})
    _, samples = preview_cleaning(nullable, "缺失值填充", ["数量"], method="固定值", value="1")
    assert samples.iloc[0]["原值"] == "（缺失）"
    assert samples.iloc[0]["新值"] == "1"


def test_failed_candidate_validation_keeps_current_state(monkeypatch):
    import app.core.data_manager as manager_module

    manager = DataManager()
    manager.load(pd.DataFrame({"姓名": [" Alice "]}), {"name": "demo.csv"})
    original = manager.frame
    change, _ = preview_cleaning(original, "文本去除前后空格", ["姓名"])
    records = len(manager.records)

    def fail(*args):
        raise RuntimeError("检测失败")

    monkeypatch.setattr(manager_module, "detect_quality", fail)
    with pytest.raises(RuntimeError, match="检测失败"):
        manager.commit_clean("文本去除前后空格", change)
    assert manager.frame is original
    assert len(manager.undo) == 0 and not manager.dirty
    assert len(manager.records) == records
