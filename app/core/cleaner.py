"""纯函数清洗：返回新数据，任何失败都不改变传入数据。"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import numpy as np
import pandas as pd
from app.utils.helpers import missing_mask, numeric_values, date_values

OPERATIONS = [
    "删除重复行", "删除空行", "缺失值填充", "删除高缺失字段",
    "文本去除前后空格", "大小写转换", "文本批量替换", "数据类型转换",
    "日期格式统一", "删除指定行", "删除指定列", "字段重命名",
]
WHOLE_TABLE_OPERATIONS = frozenset({
    "删除重复行", "删除空行", "删除高缺失字段", "删除指定行",
})
DATE_FORMATS = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "YYYY/MM/DD": "%Y/%m/%d",
    "YYYY-MM-DD HH:mm:ss": "%Y-%m-%d %H:%M:%S",
}


@dataclass
class CleanResult:
    frame: pd.DataFrame
    affected: int
    columns: list
    description: str


def parse_rows(text, length):
    """解析 1,3-5 这样的当前数据行号，严格限制在有效范围内。"""
    rows = set()
    try:
        for part in text.replace("，", ",").split(","):
            bounds = [int(v.strip()) for v in part.strip().split("-")]
            if len(bounds) not in (1, 2):
                raise ValueError
            start, end = bounds[0], bounds[-1]
            if start < 1 or end < start or end > length:
                raise ValueError
            rows.update(range(start - 1, end))
    except (ValueError, TypeError) as exc:
        raise ValueError("行号无效，请使用 1,3-5 格式，且不能超出当前数据范围。") from exc
    return sorted(rows)


def convert_series(series, target):
    miss = missing_mask(series)
    if target == "整数":
        converted = []
        for value, empty in zip(series, miss):
            if empty:
                converted.append(pd.NA)
                continue
            try:
                if isinstance(value, (bool, np.bool_)):
                    number = Decimal(int(value))
                else:
                    number = Decimal(str(value).strip())
            except InvalidOperation as exc:
                raise ValueError(f"不能转换为数值，例如：{value!s}。原数据已保留。") from exc
            if not number.is_finite():
                raise ValueError(f"不能转换为有限数值，例如：{value!s}。原数据已保留。")
            if number != number.to_integral_value():
                raise ValueError("存在带小数的值，转换为整数会损失精度；请先处理这些值。")
            if number < -(2 ** 63) or number >= 2 ** 63:
                raise ValueError("数值超出 64 位整数范围。")
            converted.append(int(number))
        # 不经 float 中转，保留空值及 64 位整数的全部有效数字。
        return pd.Series(converted, index=series.index, dtype="Int64", name=series.name)
    if target == "小数":
        values = numeric_values(series)
        bad = ~miss & values.isna()
        if bad.any():
            raise ValueError(f"有 {int(bad.sum())} 个值不能转换为数值，例如：{series[bad].iloc[0]!s}。原数据已保留。")
        return values.astype("Float64")
    if target == "字符串":
        return series.mask(miss, pd.NA).astype("string")
    if target == "日期":
        values = date_values(series)
        bad = ~miss & values.isna()
        if bad.any():
            raise ValueError(f"有 {int(bad.sum())} 个值不是有效日期，例如：{series[bad].iloc[0]!s}。请先修正。")
        return values
    raise ValueError("请选择有效的目标类型。")


def fill_missing(series, method, value):
    clean = series.mask(missing_mask(series), pd.NA)
    if method in ("均值", "中位数"):
        numbers = numeric_values(series)
        if (clean.notna() & numbers.isna()).any():
            raise ValueError("此字段包含非数值，请先修正后再使用均值或中位数。")
        if numbers.notna().sum() == 0:
            raise ValueError("此字段没有可用于计算的数值。")
        fill = numbers.mean() if method == "均值" else numbers.median()
        return numbers.astype("Float64").fillna(fill)
    if method == "众数":
        modes = clean.mode()
        if modes.empty:
            raise ValueError("全空字段没有众数，请选择固定值。")
        return clean.fillna(modes.iloc[0])
    if method == "前向填充":
        return clean.ffill()
    if method == "后向填充":
        return clean.bfill()
    if method == "固定值":
        if value is None or not str(value).strip():
            raise ValueError("固定填充值不能为空。")
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            number = pd.to_numeric(value, errors="coerce")
            if pd.notna(number) and np.isfinite(number):
                if pd.api.types.is_integer_dtype(series) and number % 1:
                    return clean.astype("Float64").fillna(number)
                return clean.fillna(number)
        return clean.astype(object).fillna(value)
    raise ValueError("请选择有效的填充方式。")


def clean_data(frame, operation, columns=None, **params):
    if operation not in OPERATIONS:
        raise ValueError("不支持的清洗操作。")
    columns = list(columns or [])
    if any(col not in frame.columns for col in columns):
        raise ValueError("所选字段不存在，请刷新字段列表。")
    if operation not in WHOLE_TABLE_OPERATIONS and not columns:
        raise ValueError("请至少选择一个字段。")
    result = frame.copy(deep=True)
    affected = 0
    if operation == "删除重复行":
        result = result.drop_duplicates()
        affected = len(frame) - len(result)
    elif operation == "删除空行":
        if len(frame.columns):
            missing_columns = [missing_mask(frame[column]) for column in frame.columns]
            mask = pd.concat(missing_columns, axis=1).all(axis=1)
        else:
            mask = pd.Series(True, index=frame.index)
        result = result.loc[~mask]
        affected = int(mask.sum())
    elif operation == "删除高缺失字段":
        threshold = params.get("threshold", .3)
        if not 0 < threshold <= 1:
            raise ValueError("缺失率阈值应大于 0 且不超过 100%。")
        columns = [c for c in frame.columns if len(frame) and missing_mask(frame[c]).mean() >= threshold]
        if columns and len(columns) == len(frame.columns):
            raise ValueError("操作会删除全部字段，请至少保留一个字段。")
        result = result.drop(columns=columns)
        affected = len(frame) if columns else 0
    elif operation == "删除指定行":
        rows = parse_rows(params.get("rows", ""), len(frame))
        result = result.iloc[~np.isin(np.arange(len(result)), rows)]
        affected = len(rows)
    elif operation == "删除指定列":
        if len(columns) == len(frame.columns):
            raise ValueError("请至少保留一个字段。")
        result = result.drop(columns=columns)
        affected = len(frame)
    elif operation == "字段重命名":
        name = str(params.get("name", "")).strip()
        if len(columns) != 1 or not name:
            raise ValueError("重命名需选择一个字段并输入非空的新名称。")
        if name in frame.columns and name != columns[0]:
            raise ValueError("新字段名已存在，请使用不重复的名称。")
        result = result.rename(columns={columns[0]: name})
        affected = len(frame) if name != columns[0] else 0
    else:
        changed = pd.Series(False, index=frame.index)
        for col in columns:
            original = frame[col]
            if operation == "缺失值填充":
                result[col] = fill_missing(original, params.get("method", "固定值"), params.get("value"))
            elif operation == "文本去除前后空格":
                result[col] = original.map(lambda v: v.strip() if isinstance(v, str) else v)
            elif operation == "大小写转换":
                upper = params.get("case", "全部大写") == "全部大写"
                convert_case = str.upper if upper else str.lower
                result[col] = original.map(
                    lambda value: convert_case(value) if isinstance(value, str) else value
                )
            elif operation == "文本批量替换":
                old, new = params.get("old", ""), params.get("new", "")
                if not old:
                    raise ValueError("待替换文本不能为空。")
                result[col] = original.map(lambda v: v.replace(old, new) if isinstance(v, str) else v)
            elif operation == "数据类型转换":
                result[col] = convert_series(original, params.get("target"))
            elif operation == "日期格式统一":
                date_format = params.get("date_format", "YYYY-MM-DD")
                if date_format not in DATE_FORMATS:
                    raise ValueError("不支持的日期格式。")
                result[col] = convert_series(original, "日期").dt.strftime(DATE_FORMATS[date_format]).astype("string")
            old_null, new_null = original.isna(), result[col].isna()
            comparable = ~old_null & ~new_null
            equal = old_null & new_null
            equal.loc[comparable] = original.loc[comparable].astype(object).eq(result.loc[comparable, col].astype(object))
            changed |= ~equal
            if original.dtype != result[col].dtype:
                changed |= ~missing_mask(original)
        affected = int(changed.sum())
    description = operation + (f"；字段：{'、'.join(map(str, columns))}" if columns else "")
    details = {k: v for k, v in params.items() if v is not None}
    if details:
        labels = {
            "method": "填充方式", "value": "固定值", "case": "大小写",
            "old": "原文本", "new": "新文本", "target": "目标类型",
            "rows": "数据行号", "name": "新名称", "threshold": "阈值",
            "date_format": "日期格式",
        }
        description += "；" + "，".join(f"{labels.get(k, k)}={v}" for k, v in details.items())
    return CleanResult(result.reset_index(drop=True), affected, columns, description)
