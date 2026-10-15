import pandas as pd
from pandas.testing import assert_frame_equal

from app.core.data_query import search_positions


def test_search_matches_literal_text_without_changing_data():
    frame = pd.DataFrame({"名称": ["a.b", "axb", None, "A.B"]}, index=[9, 3, 7, 1])
    original = frame.copy(deep=True)

    assert search_positions(frame, ".", -1, True).tolist() == [0, 3]
    assert search_positions(frame, "a.b", -1, True).tolist() == [0, 3]
    assert search_positions(frame, "未找到", -1, True).tolist() == []
    assert search_positions(frame, "", -1, True).tolist() == [0, 1, 2, 3]
    assert_frame_equal(frame, original)


def test_mixed_type_sort_is_stable_and_keeps_missing_last():
    frame = pd.DataFrame({"值": [2, "10", None, 2]})
    original = frame.copy(deep=True)

    assert search_positions(frame, "", 0, True).tolist() == [1, 0, 3, 2]
    assert search_positions(frame, "", 0, False).tolist() == [0, 3, 1, 2]
    assert_frame_equal(frame, original)


def test_search_then_sort_retains_original_row_positions():
    frame = pd.DataFrame({"名称": ["甲", "乙", "甲"], "数量": [8, 1, 3]})
    assert search_positions(frame, "甲", 1, True).tolist() == [2, 0]
    assert search_positions(frame.iloc[:0], "甲", 1, True).tolist() == []
