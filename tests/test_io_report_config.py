from pathlib import Path
import pandas as pd
import pytest
from app.core.file_loader import load_file, sheet_names, export_data
from app.core.data_manager import DataManager
from app.core.report_generator import generate_report, export_report
from app.core.analyzer import analyze
from app.utils.config import ConfigStore


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "gbk", "gb18030"])
def test_csv_encodings(tmp_path, encoding):
    path = tmp_path / "输入.csv"
    path.write_bytes("姓名,值\n模拟甲,1\n模拟乙,2\n".encode(encoding))
    frame, meta = load_file(path)
    assert frame.iloc[0, 0] == "模拟甲"
    assert len(frame) == 2
    assert meta["size"] > 0


def test_csv_gb18030_extension(tmp_path):
    path = tmp_path / "编码.csv"
    path.write_bytes("文字,值\n模拟😀,1\n".encode("gb18030"))
    assert load_file(path)[0].iloc[0, 0] == "模拟😀"


def test_excel_sheets_and_roundtrip(tmp_path):
    path = tmp_path / "多页.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"a": [1, 2]}).to_excel(writer, sheet_name="甲", index=False)
        pd.DataFrame({"b": [3, 4]}).to_excel(writer, sheet_name="乙", index=False)
    assert sheet_names(path) == ["甲", "乙"]
    assert load_file(path, "乙")[0].b.tolist() == [3, 4]


@pytest.mark.parametrize("suffix,content", [(".csv", b""), (".xlsx", b"broken"), (".txt", b"a\n1"), (".csv", b"a,b\n"), (".csv", b"a\n\xff\xff\xff")])
def test_invalid_files(tmp_path, suffix, content):
    path = tmp_path / ("bad" + suffix)
    path.write_bytes(content)
    with pytest.raises(ValueError):
        load_file(path)


def test_not_found():
    with pytest.raises(ValueError, match="不存在"):
        load_file("不存在.csv")


def test_legacy_xls_fixture():
    path = Path(__file__).parent / "fixtures/legacy_data.xls"
    assert sheet_names(path) == ["旧版数据"]
    frame, _ = load_file(path, "旧版数据")
    assert frame["名称"].tolist() == ["模拟甲", "模拟乙"]
    assert frame["数量"].tolist() == [10, 20]


@pytest.mark.parametrize("suffix", [".xlsx", ".csv"])
def test_export_and_overwrite_protection(tmp_path, suffix):
    frame = pd.DataFrame({"a": [1, 2], "文字": ["模拟", "=1+1"]})
    path = tmp_path / ("export" + suffix)
    export_data(frame, path)
    reloaded = load_file(path)[0]
    assert reloaded["文字"].iloc[1] == "=1+1"
    before = path.read_bytes()
    with pytest.raises(ValueError, match="确认"):
        export_data(frame, path)
    assert path.read_bytes() == before
    export_data(frame.iloc[:1], path, allow_overwrite=True)
    assert len(load_file(path)[0]) == 1


def test_failed_export_preserves_existing_file(tmp_path, monkeypatch):
    path = tmp_path / "data.csv"
    path.write_text("原始内容", encoding="utf-8")
    def fail(*args, **kwargs):
        raise PermissionError("模拟写入失败")
    monkeypatch.setattr(pd.DataFrame, "to_csv", fail)
    with pytest.raises(PermissionError):
        export_data(pd.DataFrame({"a": [1]}), path, allow_overwrite=True)
    assert path.read_text(encoding="utf-8") == "原始内容"
    assert not list(tmp_path.glob(".dataclean-*"))


def test_report_escape_and_comparison(sample, tmp_path):
    manager = DataManager()
    manager.load(sample, {"name": "<script>alert(1)</script>.csv"})
    manager.apply("删除重复行")
    html = generate_report(manager)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "一致性" in html and "清洗前后对比" in html
    assert "无效日期" in html
    path = tmp_path / "报告.html"
    export_report(manager, path)
    assert path.read_text(encoding="utf-8") == html


def test_statistics():
    output = analyze(pd.DataFrame({"数值": [1, 2, 3, None], "文本": ["甲", "甲", "乙", None]}))
    numeric = output["numeric"].iloc[0]
    assert numeric["平均值"] == 2
    assert numeric["中位数"] == 2
    assert numeric["标准差"] == 1
    assert numeric["25%分位数"] == 1.5
    text = output["text"].iloc[0]
    assert text["最高频值出现次数"] == 2
    assert text["缺失数量"] == 1
    assert output["histograms"]["数值"][0].sum() == 3


def test_persistent_settings_and_corrupt_recovery(tmp_path):
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    store.save({"missing_threshold": .45, "undo_limit": 5})
    store.add_recent("测试.csv")
    loaded = ConfigStore(path)
    assert loaded.values["missing_threshold"] == .45
    assert loaded.values["recent_files"] == ["测试.csv"]
    with pytest.raises(ValueError):
        store.save({"iqr_factor": -1})
    path.write_text("{broken", encoding="utf-8")
    fallback = ConfigStore(path)
    assert fallback.warning
    assert fallback.values["missing_threshold"] == .3
