"""输出三个原样例的可复核检测报告、清洗数据及操作记录，源文件保持不变。"""
from hashlib import sha256
import json
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.data_manager import DataManager
from app.core.file_loader import load_file, export_data
from app.core.report_generator import export_report


def main():
    output = ROOT / "verification/release_check"
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, sheet in [("student_data.xlsx", "学员数据"), ("sales_data.csv", None), ("customer_data.xlsx", "客户数据")]:
        source = ROOT / "samples" / name
        digest = sha256(source.read_bytes()).hexdigest()
        directory = output / source.stem
        directory.mkdir(exist_ok=True)
        manager = DataManager()
        manager.load(*load_file(source, sheet))
        before = manager.result
        assert before.metrics["missing"] == 73 and before.metrics["duplicates"] == 3
        assert before.metrics["outliers"] == 9 and before.score["score"] == 96.51
        export_report(manager, directory / "原始质量报告.html")
        manager.apply("删除重复行")
        manager.apply("文本去除前后空格", ["名称"])
        manager.apply("缺失值填充", ["备注"], method="固定值", value="未填写")
        manager.apply("数据类型转换", [manager.frame.columns[3]], target="小数")
        assert manager.result.score["score"] > before.score["score"]
        export_report(manager, directory / "清洗后质量报告.html")
        for extension in ("xlsx", "csv"):
            target = directory / ("清洗结果." + extension)
            export_data(manager.frame, target, allow_overwrite=True)
            restored, _ = load_file(target)
            assert restored.shape == manager.frame.shape
        export_data(pd.DataFrame([r.to_dict() for r in manager.records]), directory / "操作记录.csv", allow_overwrite=True)
        results[name] = {"before": before.metrics, "after": manager.result.metrics,
                         "score_before": before.score["score"], "score_after": manager.result.score["score"],
                         "issue_count": before.issue_count, "source_sha256": digest}
        assert sha256(source.read_bytes()).hexdigest() == digest
        print(name, "检测、清洗、报告与双格式导出通过", flush=True)
    (output / "samples_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
