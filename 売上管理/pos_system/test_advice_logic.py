"""advice_logic.py のユニットテスト"""
from datetime import date

from advice_logic import get_prev_month_range


def test_get_prev_month_range_full_month():
    result = get_prev_month_range(date(2026, 6, 1), date(2026, 6, 30))
    assert result == (date(2026, 5, 1), date(2026, 5, 31))


def test_get_prev_month_range_year_boundary():
    result = get_prev_month_range(date(2026, 1, 1), date(2026, 1, 31))
    assert result == (date(2025, 12, 1), date(2025, 12, 31))


def test_get_prev_month_range_not_full_month():
    result = get_prev_month_range(date(2026, 6, 1), date(2026, 6, 15))
    assert result is None


def test_get_prev_month_range_multi_month():
    result = get_prev_month_range(date(2026, 5, 1), date(2026, 6, 30))
    assert result is None
