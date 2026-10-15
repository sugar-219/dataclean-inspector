"""使用本地 HTML 模板生成可独立浏览和打印的质量报告。"""
from html import escape
from string import Template
from pathlib import Path
from app import APP_NAME
from app.utils.helpers import resource_path
from app.core.file_loader import atomic_write


def table(frame):
    return frame.to_html(index=False, border=0, escape=True, float_format=lambda v: f"{v:.2f}") if not frame.empty else "<p>暂无数据</p>"


def generate_report(manager):
    result = manager.result
    if result is None:
        raise ValueError("请先导入数据并完成质量检测。")
    issue_rows = []
    for issue in result.issues:
        locations = ", ".join(map(str, issue.rows[:50])) + ("…" if issue.count > 50 else "")
        cells = [issue.kind, issue.column, issue.severity, str(issue.count), locations, issue.description, issue.suggestion]
        issue_rows.append("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in cells) + "</tr>")
    score = result.score
    dimensions = "".join(f"<tr><td>{name}</td><td>{value:.2f}</td><td>{score['weights'][name]:.0%}</td><td>{score['deductions'][name]:.2f}</td></tr>" for name, value in score["dimensions"].items())
    fields = result.fields.copy()
    if not fields.empty:
        fields["缺失率"] = fields["缺失率"].map(lambda v: f"{v:.1%}")
    template = Template(resource_path("resources/report_template.html").read_text(encoding="utf-8"))
    return template.substitute(app_name=APP_NAME, detected_at=result.detected_at,
        filename=escape(manager.metadata.get("name", "未命名数据")), sheet=escape(str(manager.metadata.get("sheet") or "默认")),
        rows=result.metrics["rows"], columns=result.metrics["columns"], score=score["score"], rating=score["rating"],
        issue_count=result.issue_count, missing=result.metrics["missing"], duplicates=result.metrics["duplicates"], outliers=result.metrics["outliers"],
        dimensions=dimensions, field_table=table(fields), issues="".join(issue_rows) or '<tr><td colspan="7">未发现问题</td></tr>',
        comparison=table(manager.comparison()), threshold=f"{manager.settings.get('missing_threshold', .3):.0%}", factor=manager.settings.get("iqr_factor", 1.5))


def export_report(manager, path):
    html = generate_report(manager)
    atomic_write(Path(path), lambda temporary: temporary.write_text(html, encoding="utf-8"))
