"""生成清洗候选结果和有限的改动样例，不修改当前数据。"""
import numpy as np
import pandas as pd
from app.core.cleaner import clean_data

PREVIEW_LIMIT = 100


def preview_cleaning(frame, operation, columns=None, **params):
    change = clean_data(frame, operation, columns, **params)
    samples = []

    def value_text(value):
        if pd.isna(value):
            return "（缺失）"
        return repr(value) if isinstance(value, str) else str(value)

    def add(row, column, before, after):
        samples.append({"数据行号": row, "字段": column, "原值": before, "新值": after})

    if operation == "字段重命名":
        for before, after in zip(frame.columns, change.frame.columns):
            if before != after:
                add("全部行", "字段名", str(before), str(after))
    elif len(change.frame.columns) < len(frame.columns):
        for column in frame.columns.difference(change.frame.columns, sort=False):
            if len(samples) >= PREVIEW_LIMIT:
                break
            add("全部行", str(column), "保留字段", "删除字段")
    elif len(change.frame) < len(frame):
        removed = np.flatnonzero(~frame.index.isin(change.source_index))
        for position in removed[:PREVIEW_LIMIT]:
            for column in frame.columns:
                add(int(position) + 1, str(column), value_text(frame[column].iloc[position]), "（删除此行）")
                if len(samples) >= PREVIEW_LIMIT:
                    break
            if len(samples) >= PREVIEW_LIMIT:
                break
    else:
        for column in change.columns:
            before, after = frame[column], change.frame[column]
            old_null, new_null = before.isna(), after.isna()
            equal = old_null & new_null
            comparable = ~old_null & ~new_null
            equal.loc[comparable] = before.loc[comparable].astype(object).eq(after.loc[comparable].astype(object))
            changed = ~equal
            if before.dtype != after.dtype:
                changed |= ~old_null | ~new_null
            for position in np.flatnonzero(changed.to_numpy(dtype=bool))[:PREVIEW_LIMIT - len(samples)]:
                add(int(position) + 1, str(column), value_text(before.iloc[position]), value_text(after.iloc[position]))
            if len(samples) >= PREVIEW_LIMIT:
                break
    return change, pd.DataFrame(samples, columns=["数据行号", "字段", "原值", "新值"])
