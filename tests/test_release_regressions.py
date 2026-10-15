"""发布检查中发现的数据保真及异常输入回归。"""
import json
import pandas as pd
import pytest
from openpyxl import load_workbook
from app.core.cleaner import convert_series
from app.core.file_loader import load_file, export_data
from app.utils.config import ConfigStore


@pytest.mark.parametrize("number", ["9007199254740993", "9223372036854775807", "-9223372036854775808"])
def test_integer_conversion_preserves_all_digits_with_missing(number):
    converted = convert_series(pd.Series([number, ""]), "整数")
    assert converted.iloc[0] == int(number)
    assert pd.isna(converted.iloc[1])


def test_integer_conversion_rejects_tiny_fraction():
    with pytest.raises(ValueError, match="小数"):
        convert_series(pd.Series(["1.0000000000000000001", ""]), "整数")


def test_csv_preserves_blank_data_rows(tmp_path):
    path = tmp_path / "空行.csv"
    path.write_text("名称\n模拟甲\n\n模拟乙\n", encoding="utf-8")
    frame, _ = load_file(path)
    assert len(frame) == 3
    assert frame.iloc[1, 0] == ""


def test_csv_rejects_silent_index_inference(tmp_path):
    path = tmp_path / "多余字段.csv"
    path.write_text("甲,乙\n1,2,3\n4,5,6\n", encoding="utf-8")
    with pytest.raises(ValueError, match="行列格式"):
        load_file(path)


@pytest.mark.parametrize("changes", [{"undo_limit": float("inf")}, {"show_recent": "false"}])
def test_invalid_config_falls_back_without_startup_failure(tmp_path, changes):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(changes), encoding="utf-8")
    store = ConfigStore(path)
    assert store.warning
    assert store.values["undo_limit"] == 20
    assert store.values["show_recent"] is True


def test_excel_preserves_large_integer_as_text(tmp_path):
    path = tmp_path / "长编号.xlsx"
    export_data(pd.DataFrame({"编号": pd.Series([9007199254740993, pd.NA], dtype="Int64"), "名称": ["甲", "乙"]}), path)
    book = load_workbook(path)
    assert book.active["A2"].value == "9007199254740993"
    assert book.active["A2"].data_type == "s"
    book.close()
