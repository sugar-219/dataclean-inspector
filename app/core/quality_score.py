"""可解释的四维评分。提示类问题不扣分；同一维度按单元格去重。"""


def calculate_score(rows, columns, missing, duplicates, inconsistent, invalid):
    if rows == 0 or columns == 0:
        return {"score": 0.0, "rating": "无数据", "dimensions": {}, "weights": {}, "deductions": {}}
    cells = rows * columns
    rates = {"完整性": missing / cells, "唯一性": duplicates / rows,
             "一致性": inconsistent / cells, "有效性": invalid / cells}
    weights = {"完整性": .35, "唯一性": .25, "一致性": .20, "有效性": .20}
    dimensions = {key: round(100 * (1 - min(1, max(0, value))), 2) for key, value in rates.items()}
    score = round(sum(dimensions[key] * weights[key] for key in weights), 2)
    rating = "严重"
    for minimum, label in [(90, "优秀"), (80, "良好"), (70, "一般"), (60, "较差")]:
        if score >= minimum:
            rating = label
            break
    return {"score": score, "rating": rating, "dimensions": dimensions, "weights": weights,
            "deductions": {key: round((100 - dimensions[key]) * weights[key], 2) for key in weights}}
