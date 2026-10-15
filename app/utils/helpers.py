"""共享的数据语义及资源定位；所有行号均为表头之后从 1 开始的数据行。"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype


def resource_path(relative):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / relative


def missing_mask(series):
    return series.isna() | series.map(lambda v: isinstance(v, str) and not v.strip())


def numeric_values(series):
    values = pd.to_numeric(series.mask(missing_mask(series)), errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan)


def date_values(series):
    # 不把普通编号、整数或任意文本误识别为 Unix 纳秒时间戳。
    if is_datetime64_any_dtype(series):
        return series
    text = series.astype("string").str.strip()
    shaped = text.str.match(r"^\d{4}[-/年]\d{1,2}[-/月]\d{1,2}(?:日)?(?:[ T].*)?$", na=False)
    text = text.where(shaped).str.replace("年", "-", regex=False).str.replace("月", "-", regex=False).str.replace("日", "", regex=False)
    return pd.to_datetime(text, errors="coerce", format="mixed")


def infer_type(series):
    valid = series[~missing_mask(series)]
    if valid.empty:
        return "其他"
    if is_bool_dtype(series) or valid.map(lambda x: isinstance(x, (bool, np.bool_))).all():
        return "布尔值"
    if is_datetime64_any_dtype(series):
        return "日期"
    numbers = numeric_values(valid)
    if is_numeric_dtype(series) or numbers.notna().mean() >= .7:
        return "整数" if ((numbers.dropna() % 1) == 0).all() else "浮点数"
    if date_values(valid).notna().mean() >= .7:
        return "日期"
    return "文本"


def display_value(value):
    if pd.isna(value):
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "是" if value else "否"
    return str(value)
