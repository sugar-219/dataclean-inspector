"""计算预览使用的行位置；搜索和排序不修改原始数据。"""
import numpy as np


def search_positions(frame, query, column, ascending):
    mask = np.ones(len(frame), dtype=bool)
    if query:
        mask = np.zeros(len(frame), dtype=bool)
        for name in frame.columns:
            matches = frame[name].astype("string").str.contains(
                query, case=False, regex=False, na=False
            )
            mask |= matches.to_numpy(dtype=bool)
    positions = np.flatnonzero(mask)
    if 0 <= column < len(frame.columns):
        series = frame.iloc[positions, column].reset_index(drop=True)
        try:
            order = series.sort_values(ascending=ascending, kind="stable", na_position="last").index
        except TypeError:
            order = series.astype("string").sort_values(ascending=ascending, kind="stable", na_position="last").index
        positions = positions[order.to_numpy()]
    return positions
