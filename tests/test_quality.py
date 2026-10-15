import numpy as np
import pandas as pd
import pytest
from app.core.quality_detector import detect_quality
from app.core.quality_score import calculate_score
from app.utils.helpers import infer_type


def test_missing_and_empty_strings():
    frame = pd.DataFrame({"值": [None, np.nan, "", "   ", "正常"]})
    result = detect_quality(frame)
    assert result.metrics["missing"] == 4
    assert next(i for i in result.issues if i.kind == "缺失值").rows == [1, 2, 3, 4]
    assert next(i for i in result.issues if i.kind == "空字符串").count == 2


def test_duplicate_and_whitespace(sample):
    result = detect_quality(sample)
    assert result.metrics["duplicates"] == 1
    assert next(i for i in result.issues if i.kind == "重复行").rows == [6]
    assert next(i for i in result.issues if i.kind == "前后空格").rows == [1]


def test_type_and_date_anomaly(sample):
    issues = detect_quality(sample).issues
    assert next(i for i in issues if i.kind == "数据类型异常").rows == [4]
    assert next(i for i in issues if i.kind == "日期格式异常").rows == [4]


def test_iqr_exact_bounds():
    frame = pd.DataFrame({"金额": [10, 11, 12, 13, 14, 15, 16, 1000]})
    issue = next(i for i in detect_quality(frame).issues if i.kind == "数值异常值")
    assert issue.rows == [8]
    assert issue.details["Q1"] == 11.75
    assert issue.details["下界"] == 6.5
    assert issue.details["最大值"] == 1000


def test_threshold_and_constant_and_unique():
    frame = pd.DataFrame({"编号": range(20), "状态": ["正常"] * 20, "备注": [None] * 6 + ["有"] * 14})
    issues = detect_quality(frame).issues
    assert {"常量列", "唯一值异常", "高缺失率字段"} <= {i.kind for i in issues}
    assert not any(i.kind == "高缺失率字段" for i in detect_quality(frame, {"missing_threshold": .31}).issues)


@pytest.mark.parametrize("values,expected", [([True, False], "布尔值"), ([1, 2], "整数"), ([1.2, 2.3], "浮点数"), (["a", "b"], "文本"), ([None, None], "其他"), (["2026-01-01", "2026/01/02"], "日期")])
def test_inferred_types(values, expected):
    assert infer_type(pd.Series(values)) == expected


def test_score_formula_and_bounds():
    score = calculate_score(10, 2, 2, 1, 2, 2)
    assert score["score"] == 90
    assert score["rating"] == "优秀"
    assert sum(score["deductions"].values()) == 10
    assert calculate_score(10, 2, 999, 999, 999, 999)["score"] == 0
    assert calculate_score(0, 0, 0, 0, 0, 0)["rating"] == "无数据"


def test_consistency_does_not_double_count():
    frame = pd.DataFrame({"数值": [1, 2, 3, " 未知 ", 5]})
    result = detect_quality(frame)
    assert result.metrics["inconsistent"] == 1
    assert result.score["dimensions"]["一致性"] == 80


def test_infinity_is_not_valid_numeric():
    result = detect_quality(pd.DataFrame({"数值": [1., 2., 3., 4., np.inf]}))
    assert next(i for i in result.issues if i.kind == "数据类型异常").rows == [5]


def test_empty_frame_and_all_empty_column():
    result = detect_quality(pd.DataFrame({"空": pd.Series(dtype=object)}))
    assert result.score["score"] == 0
    assert not result.issues


@pytest.mark.parametrize("dtype", ["Int64", "Float64"])
def test_nullable_numeric_missing_is_not_an_outlier(dtype):
    frame = pd.DataFrame({"值": pd.Series([1, 2, 3, 4, 5, 100, pd.NA], dtype=dtype)})
    result = detect_quality(frame)
    assert result.metrics["missing"] == 1
    assert next(i.rows for i in result.issues if i.kind == "数值异常值") == [6]


def test_date_invalid_calendar_and_numeric_ids():
    issues = detect_quality(pd.DataFrame({"日期": ["2026-01-01", "2026/02/01", "2026年03月01日", "2026-02-30"], "编号": [20260101, 20260102, 20260103, 20260104]})).issues
    assert next(i for i in issues if i.kind == "日期格式异常").rows == [4]
    assert not any(i.column == "编号" and i.kind == "日期格式异常" for i in issues)
