"""三个发布样例的真实业务链路及全部清洗操作验证。"""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from app.core.cleaner import OPERATIONS
from app.core.data_manager import DataManager
from app.core.file_loader import load_file, export_data
from app.core.report_generator import export_report
from app.utils.helpers import missing_mask

SAMPLES = ["student_data.xlsx", "sales_data.csv", "customer_data.xlsx"]
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=SAMPLES)
def sample_manager(request):
    name = request.param
    frame, metadata = load_file(ROOT / "samples" / name, "客户数据" if name.startswith("customer") else None)
    manager = DataManager()
    manager.load(frame, metadata)
    return manager


def assert_score_matches_data(manager):
    frame, metrics = manager.frame, manager.result.metrics
    assert metrics["missing"] == sum(int(missing_mask(frame[c]).sum()) for c in frame.columns)
    assert metrics["duplicates"] == int(frame.duplicated().sum())
    cells = frame.size
    expected = (.35 * round(100 * (1 - metrics["missing"] / cells), 2)
                + .25 * round(100 * (1 - metrics["duplicates"] / len(frame)), 2)
                + .20 * round(100 * (1 - metrics["inconsistent"] / cells), 2)
                + .20 * round(100 * (1 - metrics["outliers"] / cells), 2))
    assert manager.result.score["score"] == round(expected, 2)


def test_three_samples_exact_quality_results(sample_manager):
    manager = sample_manager
    result = manager.result
    assert manager.frame.shape == (123, 8)
    assert result.metrics == {"rows": 123, "columns": 8, "missing": 73, "duplicates": 3,
                              "outliers": 9, "inconsistent": 5, "invalid": 9}
    assert result.score["score"] == 96.51
    assert len(result.issues) == 31
    assert next(i.rows for i in result.issues if i.kind == "重复行") == [121, 122, 123]
    assert next(i.rows for i in result.issues if i.kind == "数据类型异常") == [3]
    assert next(i.rows for i in result.issues if i.kind == "日期格式异常") == [5, 9]
    numbers = pd.to_numeric(manager.frame.iloc[:, 3], errors="coerce")
    q1, q3 = numbers.quantile([.25, .75])
    expected = (np.flatnonzero((numbers < q1 - 1.5 * (q3 - q1)) | (numbers > q3 + 1.5 * (q3 - q1))) + 1).tolist()
    assert next(i.rows for i in result.issues if i.kind == "数值异常值") == expected
    assert 4 in expected
    assert_score_matches_data(manager)


@pytest.mark.parametrize("operation", OPERATIONS)
def test_every_cleaning_operation_mutates_and_undo_restores(sample_manager, operation):
    manager = sample_manager
    amount, date = manager.frame.columns[3:5]
    if operation == "日期格式统一":
        manager.apply("文本批量替换", [date], old="2026-99-40", new="2026-01-05")
        manager.apply("文本批量替换", [date], old="abc", new="2026-01-09")
    cases = {"删除重复行": ([], {}), "删除空行": ([], {}),
        "缺失值填充": (["备注"], {"method": "固定值", "value": "未填写"}),
        "删除高缺失字段": ([], {"threshold": .3}), "文本去除前后空格": (["名称"], {}),
        "大小写转换": (["类别"], {"case": "全部小写"}),
        "文本批量替换": (["名称"], {"old": "模拟", "new": "演示"}),
        "数据类型转换": ([amount], {"target": "小数"}),
        "日期格式统一": ([date], {"date_format": "YYYY/MM/DD"}),
        "删除指定行": ([], {"rows": "1,3-5"}), "删除指定列": (["备注"], {}),
        "字段重命名": (["名称"], {"name": "记录名称"})}
    before = manager.frame.copy(deep=True)
    before_score = manager.result.score.copy()
    previous_result = manager.result
    columns, params = cases[operation]
    change = manager.apply(operation, columns, **params)
    assert not manager.frame.equals(before), operation
    assert change.affected > 0
    assert manager.result is not previous_result
    assert_score_matches_data(manager)
    if operation in ("删除重复行", "删除空行", "缺失值填充"):
        assert manager.result.score["score"] > before_score["score"]
    manager.undo_last()
    assert_frame_equal(manager.frame, before)
    assert manager.result.score == before_score


def test_clean_report_export_roundtrip(sample_manager, tmp_path):
    manager = sample_manager
    initial = manager.result.score["score"]
    manager.apply("删除重复行")
    manager.apply("文本去除前后空格", ["名称"])
    manager.apply("缺失值填充", ["备注"], method="固定值", value="未填写")
    assert manager.result.score["score"] > initial
    assert manager.baseline.score["score"] == initial
    assert_score_matches_data(manager)
    for suffix in (".csv", ".xlsx"):
        path = tmp_path / ("清洗结果" + suffix)
        export_data(manager.frame, path)
        restored, _ = load_file(path)
        assert restored.shape == manager.frame.shape
        for col in manager.frame:
            before, after = manager.frame[col], restored[col]
            pd.testing.assert_series_equal(missing_mask(before), missing_mask(after), check_names=False)
            number_before = pd.to_numeric(before.mask(missing_mask(before)), errors="coerce")
            number_after = pd.to_numeric(after.mask(missing_mask(after)), errors="coerce")
            numeric = number_before.notna()
            np.testing.assert_allclose(number_before[numeric], number_after[numeric], rtol=1e-12)
            text = ~numeric & ~missing_mask(before)
            assert before[text].astype(str).tolist() == after[text].astype(str).tolist()
    report = tmp_path / "检测报告.html"
    export_report(manager, report)
    content = report.read_text(encoding="utf-8")
    for expected in [manager.metadata["name"], "清洗前后对比", "评分组成", "建议清洗措施", str(manager.result.score["score"])]:
        assert expected in content
    assert '<script' not in content.lower()
    assert 'src="http' not in content.lower()
