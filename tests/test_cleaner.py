import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from app.core.cleaner import clean_data, parse_rows
from app.core.data_manager import DataManager


def test_duplicates_and_empty_rows():
    frame = pd.DataFrame({"a": ["x", "x", "", None], "b": [1, 1, " ", None]})
    assert len(clean_data(frame, "删除重复行").frame) == 3
    change = clean_data(frame, "删除空行")
    assert change.affected == 2
    assert len(change.frame) == 2


@pytest.mark.parametrize("method,expected", [("固定值", 9), ("均值", 2), ("中位数", 2), ("众数", 1), ("前向填充", 1), ("后向填充", 3)])
def test_fill_methods(method, expected):
    frame = pd.DataFrame({"a": [1, None, 3]})
    result = clean_data(frame, "缺失值填充", ["a"], method=method, value=9)
    assert result.frame.loc[1, "a"] == expected
    assert pd.isna(frame.loc[1, "a"])


def test_fill_empty_string_and_non_numeric_failure():
    frame = pd.DataFrame({"a": ["x", "", " "]})
    assert clean_data(frame, "缺失值填充", ["a"], method="固定值", value="z").frame.a.tolist() == ["x", "z", "z"]
    with pytest.raises(ValueError, match="非数值"):
        clean_data(frame, "缺失值填充", ["a"], method="均值")


def test_text_operations():
    frame = pd.DataFrame({"a": [" AbC ", None, 5]})
    assert clean_data(frame, "文本去除前后空格", ["a"]).frame.a.iloc[0] == "AbC"
    assert clean_data(frame, "大小写转换", ["a"], case="全部小写").frame.a.iloc[0] == " abc "
    assert clean_data(frame, "大小写转换", ["a"], case="全部大写").frame.a.iloc[0] == " ABC "
    assert clean_data(frame, "文本批量替换", ["a"], old="AbC", new="替换").frame.a.iloc[0] == " 替换 "
    assert clean_data(frame, "文本批量替换", ["a"], old="AbC", new="").frame.a.iloc[0] == "  "


@pytest.mark.parametrize("target,dtype", [("整数", "Int64"), ("小数", "Float64"), ("字符串", "string")])
def test_convert_types(target, dtype):
    frame = pd.DataFrame({"a": ["1", "2", ""]})
    result = clean_data(frame, "数据类型转换", ["a"], target=target)
    assert str(result.frame.a.dtype) == dtype
    assert pd.isna(result.frame.a.iloc[2])


def test_type_failure_is_atomic():
    frame = pd.DataFrame({"a": ["1", "2"], "b": ["3", "坏值"]})
    original = frame.copy(deep=True)
    with pytest.raises(ValueError, match="不能转换"):
        clean_data(frame, "数据类型转换", ["a", "b"], target="整数")
    assert_frame_equal(frame, original)
    with pytest.raises(ValueError, match="小数"):
        clean_data(pd.DataFrame({"a": [1.5]}), "数据类型转换", ["a"], target="整数")


def test_date_format_and_failure():
    frame = pd.DataFrame({"date": ["2026/1/2", "2026-02-03", None]})
    result = clean_data(frame, "日期格式统一", ["date"], date_format="YYYY-MM-DD")
    assert result.frame.date.iloc[0] == "2026-01-02"
    assert pd.isna(result.frame.date.iloc[2])
    with pytest.raises(ValueError, match="有效日期"):
        clean_data(pd.DataFrame({"date": ["abc"]}), "数据类型转换", ["date"], target="日期")


def test_columns_rename_and_rows():
    frame = pd.DataFrame({"a": [1, None, None, None], "b": [1, 2, 3, 4]})
    assert clean_data(frame, "删除高缺失字段", threshold=.5).frame.columns.tolist() == ["b"]
    assert clean_data(frame, "删除指定列", ["a"]).frame.columns.tolist() == ["b"]
    assert clean_data(frame, "字段重命名", ["a"], name="c").frame.columns.tolist() == ["c", "b"]
    assert clean_data(frame, "删除指定行", rows="1,3-4").frame.b.tolist() == [2]
    with pytest.raises(ValueError):
        clean_data(frame, "字段重命名", ["a"], name="b")
    with pytest.raises(ValueError):
        clean_data(frame, "删除指定列", ["a", "b"])
    with pytest.raises(ValueError):
        clean_data(frame, "文本去除前后空格", ["不存在"])


@pytest.mark.parametrize("text", ["0", "-1", "3-1", "100", "x", "", "1-2-3", "1,"])
def test_bad_rows(text):
    with pytest.raises(ValueError):
        parse_rows(text, 10)


def test_manager_undo_and_failure(sample):
    manager = DataManager({"undo_limit": 2})
    manager.load(sample, {"name": "测试"})
    baseline = manager.result.score["score"]
    manager.apply("删除重复行")
    first = manager.frame.copy()
    manager.apply("文本去除前后空格", ["姓名"])
    assert len(manager.undo) == 2
    manager.undo_last()
    assert_frame_equal(manager.frame, first)
    manager.undo_last()
    assert_frame_equal(manager.frame, sample)
    assert manager.result.score["score"] == baseline
    with pytest.raises(ValueError):
        manager.apply("数据类型转换", ["年龄"], target="整数")
    assert len(manager.undo) == 0
    assert_frame_equal(manager.frame, sample)


def test_history_limit_and_redetection_after_settings(sample):
    manager = DataManager({"undo_limit": 2})
    manager.load(sample, {"name": "测试"})
    for value in ["A", "B", "C"]:
        manager.apply("字段重命名", [manager.frame.columns[0]], name=value)
    assert len(manager.undo) == 2
    manager.detect({"missing_threshold": .8, "iqr_factor": 2., "undo_limit": 1})
    assert len(manager.undo) == 1
    assert manager.baseline.score["score"] == manager.result.score["score"]


def test_noop_does_not_consume_undo(sample):
    manager = DataManager()
    manager.load(sample, {"name": "测试"})
    manager.apply("字段重命名", ["姓名"], name="姓名")
    assert len(manager.undo) == 0
    assert not manager.dirty


def test_all_rows_can_be_deleted(sample):
    manager = DataManager()
    manager.load(sample, {"name": "测试"})
    manager.apply("删除指定行", rows="1-6")
    assert manager.frame.empty
    assert manager.result.score["rating"] == "无数据"
    manager.undo_last()
    assert_frame_equal(manager.frame, sample)


@pytest.mark.parametrize("stage", ["detect_quality", "analyze"])
def test_failed_undo_keeps_current_data_and_history(sample, monkeypatch, stage):
    import app.core.data_manager as manager_module

    manager = DataManager()
    manager.load(sample, {"name": "撤销验证"})
    manager.apply("删除重复行")
    current = manager.frame.copy(deep=True)
    result = manager.result
    records = len(manager.records)
    calculate = getattr(manager_module, stage)

    def fail_calculation(*args, **kwargs):
        raise RuntimeError("计算中断")

    monkeypatch.setattr(manager_module, stage, fail_calculation)
    with pytest.raises(RuntimeError, match="计算中断"):
        manager.undo_last()

    assert_frame_equal(manager.frame, current)
    assert manager.result is result
    assert manager.dirty
    assert len(manager.records) == records
    assert len(manager.undo) == 1

    monkeypatch.setattr(manager_module, stage, calculate)
    manager.undo_last()
    assert_frame_equal(manager.frame, sample)
    assert len(manager.undo) == 0
    assert not manager.dirty


def test_empty_undo_has_clear_error():
    from app.core.undo_manager import UndoManager

    history = UndoManager()
    for operation in [history.peek, history.pop]:
        with pytest.raises(ValueError, match="没有可撤销"):
            operation()


def test_undo_after_export_tracks_latest_saved_data():
    manager = DataManager()
    manager.load(pd.DataFrame({"name": [" Alice ", "Bob"]}), {"name": "demo.csv"})
    manager.apply("文本去除前后空格", ["name"])
    manager.mark_saved()
    assert not manager.dirty
    manager.undo_last()
    assert manager.dirty
    manager.apply("文本去除前后空格", ["name"])
    assert not manager.dirty


def test_undo_to_saved_state_and_new_file_reset_saved_baseline():
    manager = DataManager()
    manager.load(pd.DataFrame({"name": [" Alice "]}), {"name": "first.csv"})
    manager.apply("文本去除前后空格", ["name"])
    manager.mark_saved()
    manager.apply("大小写转换", ["name"], case="全部大写")
    assert manager.dirty
    manager.undo_last()
    assert not manager.dirty
    manager.load(pd.DataFrame({"name": [" Bob "]}), {"name": "second.csv"})
    manager.apply("文本去除前后空格", ["name"])
    manager.undo_last()
    assert not manager.dirty
