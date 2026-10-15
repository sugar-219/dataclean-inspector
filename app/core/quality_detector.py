"""十类质量规则，返回聚合问题和完整的 1 起始数据行位置。"""
from datetime import datetime
import numpy as np
import pandas as pd
from app.models.quality_issue import QualityIssue, DetectionResult
from app.core.quality_score import calculate_score
from app.utils.helpers import missing_mask, infer_type, numeric_values, date_values


def detect_quality(frame, settings=None):
    settings = settings or {}
    threshold = settings.get("missing_threshold", .3)
    factor = settings.get("iqr_factor", 1.5)
    issues, fields = [], []
    missing_total = inconsistent_total = invalid_total = outlier_total = 0
    n = len(frame)

    def add(kind, category, col, mask, description, severity, suggestion, details=None):
        rows = (np.flatnonzero(np.asarray(mask, dtype=bool)) + 1).tolist()
        if rows:
            issues.append(QualityIssue(kind, category, str(col), rows, description, severity, suggestion, details or {}))

    duplicate = frame.duplicated(keep="first") if len(frame.columns) else pd.Series(False, index=frame.index)
    duplicate_count = int(duplicate.sum())
    add("重复行", "重复值", "整行", duplicate, "与前面记录完全相同（保留第一条）", "警告", "删除重复行")
    for col in frame.columns:
        series = frame[col]
        miss = missing_mask(series)
        blank = series.map(lambda x: isinstance(x, str) and not x.strip())
        spaces = series.map(lambda x: isinstance(x, str) and bool(x.strip()) and x != x.strip())
        inferred = infer_type(series)
        valid = ~miss
        valid_count = int(valid.sum())
        unique = int(series[valid].nunique())
        missing_count = int(miss.sum())
        ratio = missing_count / n if n else 0
        type_bad = pd.Series(False, index=series.index)
        date_bad = type_bad.copy()
        outliers = type_bad.copy()
        add("缺失值", "缺失值", col, miss, f"缺失 {missing_count} 个，占 {ratio:.1%}", "严重", "填充缺失值或删除无效记录")
        add("空字符串", "缺失值", col, blank, "空字符串或仅由空白字符组成", "警告", "按缺失值填充或删除空行")
        add("前后空格", "格式异常", col, spaces, "文本首尾包含多余空白", "警告", "文本去除前后空格")
        if inferred in ("整数", "浮点数"):
            numbers = numeric_values(series)
            type_bad = valid & numbers.isna()
            add("数据类型异常", "类型异常", col, type_bad, "至少 70% 非空值为有限数值，其余值无法解析", "严重", "检查原值，再批量替换或修正数值")
            if numbers.notna().sum() >= 4:
                q1, q3 = numbers.quantile([.25, .75])
                low, high = q1 - factor * (q3 - q1), q3 + factor * (q3 - q1)
                outliers = (numbers.lt(low) | numbers.gt(high)).fillna(False)
                add("数值异常值", "异常值", col, outliers, f"IQR 正常区间 [{low:.4g}, {high:.4g}]", "警告", "核实异常数值，确认后替换或删除对应行",
                    {"Q1": float(q1), "Q3": float(q3), "IQR系数": factor, "下界": float(low), "上界": float(high),
                     "最小值": float(numbers.min()), "最大值": float(numbers.max()), "异常比例": float(outliers.sum() / n) if n else 0})
        elif inferred == "日期":
            date_bad = valid & date_values(series).isna()
            add("日期格式异常", "格式异常", col, date_bad, "至少 70% 非空值为日期，其余值为无效日期", "严重", "修正无效日期后统一日期格式")
        if valid_count >= 10:
            unique_ratio = unique / valid_count
            if unique_ratio >= .95 or unique_ratio <= .05:
                add("唯一值异常", "其他", col, valid, f"非空唯一值占比 {unique_ratio:.1%}；需结合业务判断", "提示", "编号字段高唯一率、分类字段低唯一率可能正常，不自动清洗")
        if unique == 1:
            add("常量列", "其他", col, valid, "仅有一个唯一非空值", "提示", "确认是否需要保留此字段")
        if n and ratio >= threshold and missing_count:
            add("高缺失率字段", "其他", col, miss, f"缺失率 {ratio:.1%}，达到阈值 {threshold:.0%}", "警告", "评估删除高缺失字段或补齐数据")
        missing_total += missing_count
        inconsistent_total += int((spaces | type_bad | date_bad).sum())
        invalid_total += int(outliers.sum())
        outlier_total += int(outliers.sum())
        fields.append({"字段名": str(col), "推断类型": inferred, "非空数量": valid_count, "空值数量": missing_count,
                       "缺失率": ratio, "唯一值数量": unique, "异常值数量": int(outliers.sum()),
                       "类型异常数量": int(type_bad.sum()), "日期异常数量": int(date_bad.sum())})
    metrics = {"rows": n, "columns": len(frame.columns), "missing": missing_total, "duplicates": duplicate_count,
               "outliers": outlier_total, "inconsistent": inconsistent_total, "invalid": invalid_total}
    score = calculate_score(n, len(frame.columns), missing_total, duplicate_count, inconsistent_total, invalid_total)
    return DetectionResult(issues, pd.DataFrame(fields, columns=["字段名", "推断类型", "非空数量", "空值数量", "缺失率", "唯一值数量", "异常值数量", "类型异常数量", "日期异常数量"]), metrics, score,
                           datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
