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


def _pct_change(cur: float, prev: float) -> str:
    """前月比の増減率を文字列で返す。前月実績がゼロなら比較不可扱い"""
    if prev == 0:
        return "比較不可（前月実績なし）"
    rate = (cur - prev) / prev * 100
    sign = "+" if rate >= 0 else ""
    return f"{sign}{rate:.1f}%"


def _cat_frame(df: pd.DataFrame) -> pd.DataFrame:
    """部門別DataFrameから「合計」行を除き、カテゴリー名をインデックスにする"""
    if df.empty or "カテゴリー" not in df.columns:
        return pd.DataFrame(columns=["売上", "荒利", "荒利率"])
    return df[df["カテゴリー"] != "合計"].set_index("カテゴリー")[["売上", "荒利", "荒利率"]]


def build_metrics_summary(
    store_label: str,
    period_label: str,
    cur_totals: dict,
    prev_totals: dict,
    cur_bumon: pd.DataFrame,
    prev_bumon: pd.DataFrame,
) -> str:
    """当月/前月の店舗合計・部門別データから、AIに渡す数値サマリーのテキストを組み立てる"""
    lines = [f"【{store_label}　{period_label}】"]

    cur_rate = cur_totals["profit"] / cur_totals["sales"] * 100 if cur_totals["sales"] else 0
    prev_rate = prev_totals["profit"] / prev_totals["sales"] * 100 if prev_totals["sales"] else 0
    cur_spend = cur_totals["sales"] / cur_totals["customers"] if cur_totals["customers"] else 0
    prev_spend = prev_totals["sales"] / prev_totals["customers"] if prev_totals["customers"] else 0

    lines.append("■ 全体実績（当月 / 前月 / 増減率）")
    lines.append(
        f"- 売上: {cur_totals['sales']:,.0f}円 / {prev_totals['sales']:,.0f}円 / "
        f"{_pct_change(cur_totals['sales'], prev_totals['sales'])}"
    )
    lines.append(
        f"- 荒利: {cur_totals['profit']:,.0f}円 / {prev_totals['profit']:,.0f}円 / "
        f"{_pct_change(cur_totals['profit'], prev_totals['profit'])}"
    )
    lines.append(f"- 荒利率: {cur_rate:.1f}% / {prev_rate:.1f}%")
    lines.append(
        f"- 客数: {cur_totals['customers']:,.0f}人 / {prev_totals['customers']:,.0f}人 / "
        f"{_pct_change(cur_totals['customers'], prev_totals['customers'])}"
    )
    lines.append(f"- 客単価: {cur_spend:,.0f}円 / {prev_spend:,.0f}円")

    cur_cat = _cat_frame(cur_bumon)
    prev_cat = _cat_frame(prev_bumon)
    merged = cur_cat.join(prev_cat, how="outer", lsuffix="_cur", rsuffix="_prev")

    new_cats = merged[merged["売上_prev"].isna()].index.tolist()
    gone_cats = merged[merged["売上_cur"].isna()].index.tolist()

    common = merged.dropna(subset=["売上_cur", "売上_prev"]).copy()
    common["荒利率差"] = common["荒利率_cur"] - common["荒利率_prev"]
    common["売上差"] = common["売上_cur"] - common["売上_prev"]

    def _section(title: str, rows: pd.DataFrame, kind: str) -> None:
        lines.append(f"■ {title}（上位3）")
        if rows.empty:
            lines.append("- 該当なし")
            return
        for cat, row in rows.iterrows():
            if kind == "rate":
                lines.append(
                    f"- {cat}: 荒利率 {row['荒利率_prev']:.1%} → {row['荒利率_cur']:.1%}"
                    f"（{row['荒利率差'] * 100:+.1f}pt）"
                )
            else:
                lines.append(
                    f"- {cat}: 売上 {row['売上_prev']:,.0f}円 → {row['売上_cur']:,.0f}円"
                    f"（{row['売上差']:+,.0f}円）"
                )

    _section("荒利率が悪化した部門", common.sort_values("荒利率差").head(3), "rate")
    _section("荒利率が改善した部門", common.sort_values("荒利率差", ascending=False).head(3), "rate")
    _section("売上が減少した部門", common.sort_values("売上差").head(3), "sales")
    _section("売上が増加した部門", common.sort_values("売上差", ascending=False).head(3), "sales")

    if new_cats:
        lines.append(f"■ 当月に新規発生した部門: {', '.join(new_cats)}")
    if gone_cats:
        lines.append(f"■ 前月にあったが当月は実績なしの部門: {', '.join(gone_cats)}")

    return "\n".join(lines)
