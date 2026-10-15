"""统计与图表数据计算，允许工作线程执行。"""
import numpy as np
import pandas as pd
from app.utils.helpers import infer_type, missing_mask, numeric_values


def analyze(frame):
    numeric, text, histograms = [], [], {}
    for col in frame.columns:
        series = frame[col]
        if infer_type(series) in ("整数", "浮点数"):
            values = numeric_values(series).dropna().astype(float)
            numeric.append({"字段": col, "数量": len(values), "平均值": values.mean(), "中位数": values.median(),
                            "标准差": values.std(), "最小值": values.min(), "最大值": values.max(),
                            "25%分位数": values.quantile(.25), "75%分位数": values.quantile(.75)})
            if len(values):
                counts, edges = np.histogram(values, bins=min(30, max(1, int(np.sqrt(len(values))))))
                histograms[col] = (counts, edges)
        else:
            valid = series[~missing_mask(series)]
            counts = valid.value_counts()
            text.append({"字段": col, "唯一值数量": valid.nunique(), "最高频值": str(counts.index[0]) if len(counts) else "",
                         "最高频值出现次数": int(counts.iloc[0]) if len(counts) else 0, "缺失数量": int(missing_mask(series).sum())})
    return {"numeric": pd.DataFrame(numeric), "text": pd.DataFrame(text), "histograms": histograms}
