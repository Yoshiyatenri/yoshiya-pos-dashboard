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


import pandas as pd


def _bumon_df(rows):
    df = pd.DataFrame(rows)
    total = pd.DataFrame([{
        "カテゴリー": "合計",
        "売上": df["売上"].sum(),
        "荒利": df["荒利"].sum(),
        "荒利率": df["荒利"].sum() / df["売上"].sum(),
    }])
    return pd.concat([df, total], ignore_index=True)


def test_build_metrics_summary_basic():
    from advice_logic import build_metrics_summary

    cur = _bumon_df([
        {"カテゴリー": "駄菓子", "売上": 100000, "荒利": 30000, "荒利率": 0.30},
        {"カテゴリー": "飲料", "売上": 50000, "荒利": 10000, "荒利率": 0.20},
    ])
    prev = _bumon_df([
        {"カテゴリー": "駄菓子", "売上": 90000, "荒利": 36000, "荒利率": 0.40},
        {"カテゴリー": "飲料", "売上": 60000, "荒利": 12000, "荒利率": 0.20},
    ])
    cur_totals = {"sales": 150000, "profit": 40000, "qty": 1000, "customers": 500}
    prev_totals = {"sales": 150000, "profit": 48000, "qty": 1000, "customers": 500}

    text = build_metrics_summary("天理店", "2026年6月", cur_totals, prev_totals, cur, prev)

    assert "駄菓子" in text
    assert "荒利率が悪化した部門" in text
    assert "150,000円" in text


def test_build_metrics_summary_new_and_gone_categories():
    from advice_logic import build_metrics_summary

    cur = _bumon_df([{"カテゴリー": "新商品", "売上": 10000, "荒利": 3000, "荒利率": 0.30}])
    prev = _bumon_df([{"カテゴリー": "廃盤商品", "売上": 5000, "荒利": 1000, "荒利率": 0.20}])
    cur_totals = {"sales": 10000, "profit": 3000, "qty": 100, "customers": 50}
    prev_totals = {"sales": 5000, "profit": 1000, "qty": 50, "customers": 30}

    text = build_metrics_summary("天理店", "2026年6月", cur_totals, prev_totals, cur, prev)

    assert "新商品" in text
    assert "廃盤商品" in text
    assert "新規発生した部門" in text
    assert "実績なしの部門" in text


def test_build_metrics_summary_empty_prev_bumon():
    from advice_logic import build_metrics_summary

    cur = _bumon_df([{"カテゴリー": "駄菓子", "売上": 10000, "荒利": 3000, "荒利率": 0.30}])
    prev = pd.DataFrame()
    cur_totals = {"sales": 10000, "profit": 3000, "qty": 100, "customers": 50}
    prev_totals = {"sales": 0, "profit": 0, "qty": 0, "customers": 0}

    text = build_metrics_summary("天理店", "2026年6月", cur_totals, prev_totals, cur, prev)

    assert "比較不可" in text


def test_build_metrics_summary_customers_none_shows_no_data():
    from advice_logic import build_metrics_summary

    cur = _bumon_df([{"カテゴリー": "駄菓子", "売上": 100000, "荒利": 30000, "荒利率": 0.30}])
    prev = _bumon_df([{"カテゴリー": "駄菓子", "売上": 90000, "荒利": 27000, "荒利率": 0.30}])
    cur_totals = {"sales": 100000, "profit": 30000, "qty": 1000, "customers": None}
    prev_totals = {"sales": 90000, "profit": 27000, "qty": 900, "customers": None}

    text = build_metrics_summary("天理店", "2026年6月", cur_totals, prev_totals, cur, prev)

    assert "- 客数: データなし / データなし / 比較不可（データなし）" in text
    assert "- 客単価: データなし / データなし" in text


def test_build_metrics_summary_customers_partial_data():
    from advice_logic import build_metrics_summary

    cur = _bumon_df([{"カテゴリー": "駄菓子", "売上": 100000, "荒利": 30000, "荒利率": 0.30}])
    prev = _bumon_df([{"カテゴリー": "駄菓子", "売上": 90000, "荒利": 27000, "荒利率": 0.30}])
    cur_totals = {"sales": 100000, "profit": 30000, "qty": 1000, "customers": 500}
    prev_totals = {"sales": 90000, "profit": 27000, "qty": 900, "customers": None}

    text = build_metrics_summary("天理店", "2026年6月", cur_totals, prev_totals, cur, prev)

    assert "- 客数: 500人 / データなし / 比較不可（データなし）" in text
    assert "- 客単価: ¥200円 / データなし" in text


def test_build_metrics_summary_customers_non_numeric_value_shows_no_data():
    """customersがDB異常等で数値化できない値(例: リスト)でも落ちずに「データなし」扱いにする"""
    from advice_logic import build_metrics_summary

    cur = _bumon_df([{"カテゴリー": "駄菓子", "売上": 100000, "荒利": 30000, "荒利率": 0.30}])
    prev = _bumon_df([{"カテゴリー": "駄菓子", "売上": 90000, "荒利": 27000, "荒利率": 0.30}])
    cur_totals = {"sales": 100000, "profit": 30000, "qty": 1000, "customers": [500]}
    prev_totals = {"sales": 90000, "profit": 27000, "qty": 900, "customers": 450}

    text = build_metrics_summary("天理店", "2026年6月", cur_totals, prev_totals, cur, prev)

    assert "- 客数: データなし / 450人 / 比較不可（データなし）" in text
    assert "- 客単価: データなし / ¥200円" in text


def test_build_metrics_summary_worsened_rate_ranked_by_profit_impact():
    """売上が小さく率の下げ幅だけ大きい部門より、売上が大きく利益額への影響が大きい部門を先に出す"""
    from advice_logic import build_metrics_summary

    cur = _bumon_df([
        {"カテゴリー": "小規模ジャンル", "売上": 1000, "荒利": 100, "荒利率": 0.10},
        {"カテゴリー": "主力ジャンル", "売上": 500000, "荒利": 125000, "荒利率": 0.25},
    ])
    prev = _bumon_df([
        {"カテゴリー": "小規模ジャンル", "売上": 1000, "荒利": 500, "荒利率": 0.50},
        {"カテゴリー": "主力ジャンル", "売上": 500000, "荒利": 150000, "荒利率": 0.30},
    ])
    cur_totals = {"sales": 501000, "profit": 125100, "qty": 1000, "customers": 500}
    prev_totals = {"sales": 501000, "profit": 150500, "qty": 1000, "customers": 500}

    text = build_metrics_summary("天理店", "2026年6月", cur_totals, prev_totals, cur, prev)

    section = text.split("■ 荒利率が悪化した部門")[1].split("■ ")[0]
    assert section.index("主力ジャンル") < section.index("小規模ジャンル")
    assert "影響額" in section


def test_build_metrics_summary_no_false_deterioration_when_all_improved():
    from advice_logic import build_metrics_summary

    cur = _bumon_df([{"カテゴリー": "駄菓子", "売上": 120000, "荒利": 42000, "荒利率": 0.35}])
    prev = _bumon_df([{"カテゴリー": "駄菓子", "売上": 100000, "荒利": 30000, "荒利率": 0.30}])
    cur_totals = {"sales": 120000, "profit": 42000, "qty": 1000, "customers": 500}
    prev_totals = {"sales": 100000, "profit": 30000, "qty": 900, "customers": 450}

    text = build_metrics_summary("天理店", "2026年6月", cur_totals, prev_totals, cur, prev)

    sections = text.split("■ ")
    worse_rate_section = next(s for s in sections if s.startswith("荒利率が悪化した部門"))
    worse_sales_section = next(s for s in sections if s.startswith("売上が減少した部門"))
    assert "駄菓子" not in worse_rate_section
    assert "駄菓子" not in worse_sales_section
    assert "該当なし" in worse_rate_section
    assert "該当なし" in worse_sales_section
