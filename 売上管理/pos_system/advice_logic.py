"""AI改善提案レポート用の数値抽出ロジック（DB・Streamlit非依存）"""
import calendar
from datetime import date

import pandas as pd


def get_prev_month_range(start: date, end: date) -> tuple[date, date] | None:
    """選択期間がちょうど1か月分なら、その前月の(開始日, 終了日)を返す。それ以外はNone"""
    last_day = calendar.monthrange(start.year, start.month)[1]
    if start.day != 1 or end != date(start.year, start.month, last_day):
        return None
    if start.month == 1:
        prev_year, prev_month = start.year - 1, 12
    else:
        prev_year, prev_month = start.year, start.month - 1
    prev_last_day = calendar.monthrange(prev_year, prev_month)[1]
    return date(prev_year, prev_month, 1), date(prev_year, prev_month, prev_last_day)
