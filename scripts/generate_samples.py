"""生成可重复的纯虚构示例，不含真实个人信息。"""
from pathlib import Path
import numpy as np
import pandas as pd


def make_data(kind):
    rng = np.random.default_rng(20260908)
    n = 120
    names = {"student": ("学员编号", "模拟学员", "年龄", "成绩", "入学日期"),
             "sales": ("订单编号", "模拟商品", "数量", "销售金额", "订单日期"),
             "customer": ("客户编号", "模拟客户", "服务次数", "消费金额", "登记日期")}
    identifier, label, count, amount, date = names[kind]
    frame = pd.DataFrame({identifier: [f"SIM-{kind.upper()}-{i:04d}" for i in range(n)],
        "名称": [f"{label}{i:03d}" for i in range(n)], count: rng.integers(18, 30, n).astype(object),
        amount: rng.normal(75, 8, n).round(2).astype(object), date: pd.date_range("2026-01-01", periods=n).strftime("%Y-%m-%d").astype(object),
        "类别": ["A", "B", "C"] * 40, "状态": ["正常"] * n, "备注": [None if i % 2 else "模拟数据" for i in range(n)]})
    frame.loc[0, "名称"] = " " + label + "000 "
    frame.loc[1, "名称"] = ""
    frame.loc[2, count] = "未知"
    frame.loc[3, amount] = 99999
    frame.loc[4, date] = "2026-99-40"
    frame.loc[5, date] = "2026/01/06"
    frame.loc[6, amount] = None
    frame.loc[7, "类别"] = " a "
    frame.loc[8, date] = "abc"
    frame.loc[9, "名称"] = "   "
    frame.loc[10, :] = None
    return pd.concat([frame, frame.iloc[[15, 16, 17]]], ignore_index=True)


def generate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    make_data("student").to_excel(directory / "student_data.xlsx", index=False, sheet_name="学员数据")
    make_data("sales").to_csv(directory / "sales_data.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(directory / "customer_data.xlsx", engine="openpyxl") as writer:
        make_data("customer").to_excel(writer, index=False, sheet_name="客户数据")
        pd.DataFrame({"说明": ["所有记录均为虚构，仅用于软件演示。", "客户数据工作表包含 123 行及预置数据问题。"]}).to_excel(writer, index=False, sheet_name="数据说明")


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1] / "samples")
