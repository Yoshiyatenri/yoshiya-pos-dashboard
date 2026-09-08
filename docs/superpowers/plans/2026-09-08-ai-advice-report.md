# 月次AI改善提案レポート Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `dashboard.py`（POSデータ抽出ダッシュボード）に、月単位・店舗ごとの売上/部門別データから利益率向上・売上向上の改善提案をClaude APIで自動生成する「AI改善提案レポート」機能を追加する。

**Architecture:** 数値抽出（ルールベース）とWord出力を担う純粋ロジックは `advice_logic.py`（DB/Streamlit非依存）、Claude API呼び出しと`.docx`生成は `ai_advice.py`（anthropic/python-docxに依存、未インストール時は既存の`openpyxl`ガードと同じ try/except パターンで無効化）という2つの新規モジュールに分離する。`dashboard.py`は両モジュールを呼び出し、既存のDB接続ヘルパー（`get_conn`/`_ph`/`_fix`）を使ったSQL集計関数と、管理者専用のサイドバーUI・結果表示を追加する。

**Tech Stack:** Python 3.12, Streamlit, pandas, sqlite3/psycopg2, anthropic SDK (`claude-opus-5`), python-docx, pytest

## Global Constraints

- コメント・警告文・エラーメッセージは日本語で書く
- 認証情報（APIキー）は`config.json`に集約し、コードにハードコードしない。`config.json`は`.gitignore`済みなのでコミット対象に含めない
- 既存コードの「未インストール時はtry/exceptで機能を無効化し、他機能は動かし続ける」パターン（`_psycopg2_ok`, `_openpyxl_ok`）を新規依存（`anthropic`, `python-docx`）にも適用する
- 新規のルールベース抽出ロジック・API呼び出しロジックはStreamlit非依存のモジュールに分離し、pytestでユニットテスト可能にする（`dashboard.py`自体はUI配線のみに留め、既存の大きなファイル構成は維持する）
- モデルは`claude-opus-5`固定
- `dashboard.py`は`streamlit run`以外の方法（例: `python -c "import dashboard"`）でも例外を投げずに最後まで実行できる（`st.stop()`がbareモードでは実際には停止しないため）。この性質を壊さないよう、新規コードも既存のtry/exceptガードのパターンを踏襲する

---

### Task 1: 依存パッケージとAPIキー設定欄の追加

**Files:**
- Modify: `売上管理/pos_system/requirements.txt`
- Modify: `売上管理/pos_system/config.json`

**Interfaces:**
- Produces: `config.json`に`anthropic_api_key`キー（プレースホルダー`"XXXXXXXXXX"`）が存在すること。後続タスクの`get_anthropic_key()`がこのキーを読む

- [ ] **Step 1: python-docxをインストール**

Run: `pip install python-docx`
Expected: `Successfully installed python-docx-...`（`anthropic`は既にインストール済みのためスキップされてよい）

- [ ] **Step 2: requirements.txtに追記**

`売上管理/pos_system/requirements.txt` の内容を以下に置き換える。

```
streamlit
pandas
psycopg2-binary
anthropic
python-docx
```

- [ ] **Step 3: config.jsonにAPIキー欄を追加**

`売上管理/pos_system/config.json` の `"run_time": "07:00"` の行を以下に置き換える（末尾カンマを追加し、新しい行を挿入する）。

```json
  "run_time": "07:00",
  "anthropic_api_key": "XXXXXXXXXX"
```

実際のAPIキーをお持ちの場合は、`"XXXXXXXXXX"` の部分をそのキーに書き換えてください（このファイルはGit管理外です）。Streamlit Cloud側で運用する場合は、Cloud側のSecretsに`anthropic_api_key`を設定し、`config.json`側は`"XXXXXXXXXX"`のままで構いません。

- [ ] **Step 4: config.jsonのJSON構文を確認**

Run: `python -c "import json; json.load(open('売上管理/pos_system/config.json', encoding='utf-8')); print('OK')"`
Expected: `OK`

- [ ] **Step 5: commit（requirements.txtのみ）**

```bash
git add "売上管理/pos_system/requirements.txt"
git commit -m "$(cat <<'EOF'
feat(pos_system): AI改善提案レポート向けの依存パッケージを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

`config.json`は`.gitignore`対象のため`git add`しない（`git status`で追跡されていないことを確認してよい）。

---

### Task 2: `advice_logic.py` — 前月範囲判定

**Files:**
- Create: `売上管理/pos_system/advice_logic.py`
- Test: `売上管理/pos_system/test_advice_logic.py`

**Interfaces:**
- Produces: `get_prev_month_range(start: date, end: date) -> tuple[date, date] | None` — 後続タスク（Task 3, Task 7）で使用

- [ ] **Step 1: 失敗するテストを書く**

`売上管理/pos_system/test_advice_logic.py` を新規作成する。

```python
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd 売上管理/pos_system && python -m pytest test_advice_logic.py -v`
Expected: `ModuleNotFoundError: No module named 'advice_logic'` でFAIL

- [ ] **Step 3: 最小実装を書く**

`売上管理/pos_system/advice_logic.py` を新規作成する。

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd 売上管理/pos_system && python -m pytest test_advice_logic.py -v`
Expected: 4件すべてPASS

- [ ] **Step 5: commit**

```bash
git add "売上管理/pos_system/advice_logic.py" "売上管理/pos_system/test_advice_logic.py"
git commit -m "$(cat <<'EOF'
feat(pos_system): 月範囲から前月期間を判定するロジックを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `advice_logic.py` — 数値サマリー生成

**Files:**
- Modify: `売上管理/pos_system/advice_logic.py`
- Test: `売上管理/pos_system/test_advice_logic.py`

**Interfaces:**
- Consumes: `pd.DataFrame`（`dashboard.py`の`query_bumon_analysis()`と同じ列構成: `カテゴリー, 売数, 売上, 荒利, SKU数, 荒利率, 単価, ...`、「合計」行を含む。空の場合は列なしの空DataFrameもありうる）
- Produces: `build_metrics_summary(store_label: str, period_label: str, cur_totals: dict, prev_totals: dict, cur_bumon: pd.DataFrame, prev_bumon: pd.DataFrame) -> str` — `cur_totals`/`prev_totals`は`{"sales": float, "profit": float, "qty": float, "customers": float}`の辞書（`dashboard.py`の`get_store_totals()`の戻り値と同じ形。Task 6で使用）

- [ ] **Step 1: 失敗するテストを書く**

`売上管理/pos_system/test_advice_logic.py` の末尾に追記する。

```python
import pandas as pd

from advice_logic import build_metrics_summary


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
    cur = _bumon_df([{"カテゴリー": "駄菓子", "売上": 10000, "荒利": 3000, "荒利率": 0.30}])
    prev = pd.DataFrame()
    cur_totals = {"sales": 10000, "profit": 3000, "qty": 100, "customers": 50}
    prev_totals = {"sales": 0, "profit": 0, "qty": 0, "customers": 0}

    text = build_metrics_summary("天理店", "2026年6月", cur_totals, prev_totals, cur, prev)

    assert "比較不可" in text
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd 売上管理/pos_system && python -m pytest test_advice_logic.py -v`
Expected: 追加した3件が `ImportError: cannot import name 'build_metrics_summary'` でFAIL（前タスクの4件はPASSのまま）

- [ ] **Step 3: 実装を追加**

`売上管理/pos_system/advice_logic.py` の末尾に追記する。

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd 売上管理/pos_system && python -m pytest test_advice_logic.py -v`
Expected: 7件すべてPASS

- [ ] **Step 5: commit**

```bash
git add "売上管理/pos_system/advice_logic.py" "売上管理/pos_system/test_advice_logic.py"
git commit -m "$(cat <<'EOF'
feat(pos_system): 前月比の数値サマリー生成ロジックを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `ai_advice.py` — Claude API呼び出し

**Files:**
- Create: `売上管理/pos_system/ai_advice.py`
- Test: `売上管理/pos_system/test_ai_advice.py`

**Interfaces:**
- Consumes: `metrics_text: str`（Task 3の`build_metrics_summary()`の戻り値）
- Produces: `call_ai_advice(store_label: str, period_label: str, metrics_text: str, api_key: str) -> str`、モジュールフラグ`_anthropic_ok: bool`（Task 6・7で参照）

- [ ] **Step 1: 失敗するテストを書く**

`売上管理/pos_system/test_ai_advice.py` を新規作成する。

```python
"""ai_advice.py のユニットテスト（Claude API部分）"""
import ai_advice


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    def __init__(self, response):
        self._response = response

    def create(self, **kwargs):
        return self._response


def test_call_ai_advice_success(monkeypatch):
    fake_response = _FakeResponse("■現状分析\nテスト分析\n■改善施策\n- 施策1")

    class _FakeAnthropic:
        def __init__(self, api_key):
            self.messages = _FakeMessages(fake_response)

    monkeypatch.setattr(ai_advice.anthropic, "Anthropic", _FakeAnthropic)

    result = ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "sk-test-key")

    assert "現状分析" in result
    assert "施策1" in result


def test_call_ai_advice_missing_key():
    result = ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "")
    assert "APIキー" in result


def test_call_ai_advice_placeholder_key():
    result = ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "XXXXXXXXXX")
    assert "APIキー" in result


def test_call_ai_advice_no_package(monkeypatch):
    monkeypatch.setattr(ai_advice, "_anthropic_ok", False)
    result = ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "sk-test-key")
    assert "インストール" in result
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd 売上管理/pos_system && python -m pytest test_ai_advice.py -v`
Expected: `ModuleNotFoundError: No module named 'ai_advice'` でFAIL

- [ ] **Step 3: 最小実装を書く**

`売上管理/pos_system/ai_advice.py` を新規作成する。

```python
"""Claude APIによるAI改善提案生成 と Word(.docx)エクスポート"""
import io

try:
    import anthropic
    _anthropic_ok = True
except ImportError:
    _anthropic_ok = False

try:
    from docx import Document
    _docx_ok = True
except ImportError:
    _docx_ok = False

_SYSTEM_PROMPT = (
    "あなたは駄菓子小売チェーンの経営コンサルタントです。"
    "与えられた実績数値だけを根拠に、日本語で店長向けの改善提案を書いてください。"
    "憶測や一般論だけの助言は避け、具体的な部門名・数値に基づいて指摘してください。"
    "出力は「■現状分析」（3〜4文）と「■改善施策」（箇条書き3〜5個、それぞれ理由付き）の"
    "2つの見出しで構成してください。"
)


def call_ai_advice(store_label: str, period_label: str, metrics_text: str, api_key: str) -> str:
    """数値サマリーをもとにAI改善提案を生成する。失敗時はエラー文言を返す"""
    if not _anthropic_ok:
        return "⚠️ 生成に失敗しました（anthropicパッケージが未インストールです。`pip install anthropic`を実行してください）"
    if not api_key or "XXXXXXXXXX" in api_key:
        return "⚠️ 生成に失敗しました（Anthropic APIキーが設定されていません。config.jsonのanthropic_api_keyを確認してください）"
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-5",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"【{store_label}　{period_label}】\n{metrics_text}",
            }],
        )
        text_blocks = [block.text for block in response.content if block.type == "text"]
        advice = "\n".join(text_blocks).strip()
        return advice if advice else "⚠️ 生成に失敗しました（応答が空でした）"
    except anthropic.APIStatusError as e:
        return f"⚠️ 生成に失敗しました（APIエラー: HTTP {e.status_code}）"
    except anthropic.APIConnectionError:
        return "⚠️ 生成に失敗しました（API接続エラー。ネットワークを確認してください）"
    except Exception as e:
        return f"⚠️ 生成に失敗しました（{e}）"
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd 売上管理/pos_system && python -m pytest test_ai_advice.py -v`
Expected: 4件すべてPASS

- [ ] **Step 5: commit**

```bash
git add "売上管理/pos_system/ai_advice.py" "売上管理/pos_system/test_ai_advice.py"
git commit -m "$(cat <<'EOF'
feat(pos_system): Claude APIでAI改善提案を生成する関数を追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `ai_advice.py` — Word(.docx)エクスポート

**Files:**
- Modify: `売上管理/pos_system/ai_advice.py`
- Test: `売上管理/pos_system/test_ai_advice.py`

**Interfaces:**
- Consumes: `results: dict[str, str]`（店舗表示名 → `call_ai_advice()`の戻り値）
- Produces: `make_advice_docx(results: dict, period_label: str) -> bytes | None`（Task 7の結果表示で使用。`_docx_ok`が`False`なら`None`）

- [ ] **Step 1: 失敗するテストを書く**

`売上管理/pos_system/test_ai_advice.py` の先頭のimportに`io`を追加し、末尾に以下を追記する。

先頭のimportを以下に変更する。

```python
"""ai_advice.py のユニットテスト（Claude API部分）"""
import io

from docx import Document

import ai_advice
```

ファイル末尾に追記する。

```python
def test_make_advice_docx_contains_all_stores():
    results = {
        "天理店": "■現状分析\nテスト\n■改善施策\n- 施策1",
        "本店": "⚠️ 生成に失敗しました（APIエラー）",
    }

    data = ai_advice.make_advice_docx(results, "2026年6月")

    assert data is not None
    doc = Document(io.BytesIO(data))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "天理店" in text
    assert "本店" in text
    assert "施策1" in text
    assert "2026年6月" in text


def test_make_advice_docx_no_package(monkeypatch):
    monkeypatch.setattr(ai_advice, "_docx_ok", False)
    assert ai_advice.make_advice_docx({"店": "文"}, "2026年6月") is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd 売上管理/pos_system && python -m pytest test_ai_advice.py -v`
Expected: 追加した2件が `AttributeError: module 'ai_advice' has no attribute 'make_advice_docx'` でFAIL

- [ ] **Step 3: 実装を追加**

`売上管理/pos_system/ai_advice.py` の末尾に追記する。

```python
def make_advice_docx(results: dict, period_label: str) -> bytes | None:
    """店舗ごとのAI改善提案をまとめた.docxをバイト列で返す"""
    if not _docx_ok:
        return None
    doc = Document()
    doc.add_heading(f"AI改善提案レポート　{period_label}", level=1)
    for store_label, advice_text in results.items():
        doc.add_heading(store_label, level=2)
        for line in advice_text.split("\n"):
            doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd 売上管理/pos_system && python -m pytest test_ai_advice.py -v`
Expected: 6件すべてPASS

- [ ] **Step 5: commit**

```bash
git add "売上管理/pos_system/ai_advice.py" "売上管理/pos_system/test_ai_advice.py"
git commit -m "$(cat <<'EOF'
feat(pos_system): AI改善提案をWord(.docx)にまとめる関数を追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: `dashboard.py` — APIキー取得・店舗合計集計ヘルパー

**Files:**
- Modify: `売上管理/pos_system/dashboard.py`

**Interfaces:**
- Consumes: なし（`dashboard.py`内の既存`get_conn()`, `_ph()`, `_fix()`, `cfg`, `st`を使用）
- Produces: `get_anthropic_key() -> str`, `get_store_totals(start: str, end: str, store_db: str) -> dict`（Task 7で使用。戻り値の形はTask 3の`cur_totals`/`prev_totals`と同じ`{"sales": float, "profit": float, "qty": float, "customers": float}`）

`dashboard.py`はStreamlitのUIコードがモジュール直下で実行される構造上、`streamlit run`以外の方法で単体テストしにくい（既存の`query_data`/`query_bumon_analysis`も同様に無テスト）。本タスクも既存パターンを踏襲し、pytestではなく手動確認で進める。

- [ ] **Step 1: importを追加する**

`売上管理/pos_system/dashboard.py` の以下の箇所（openpyxlのtry/exceptブロック直後、`BASE_DIR = ...`の直前）を編集する。

変更前:
```python
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    _openpyxl_ok = True
except ImportError:
    _openpyxl_ok = False

BASE_DIR = Path(__file__).parent
```

変更後:
```python
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    _openpyxl_ok = True
except ImportError:
    _openpyxl_ok = False

from advice_logic import get_prev_month_range, build_metrics_summary
from ai_advice import call_ai_advice, make_advice_docx, _docx_ok

BASE_DIR = Path(__file__).parent
```

- [ ] **Step 2: `get_anthropic_key()`を追加する**

`_use_pg()`関数の直後、`get_conn()`関数の直前に追記する。

変更前:
```python
def _use_pg() -> bool:
    """Supabaseを使うかどうか（URLが正しく設定されている場合のみ）"""
    url = get_db_url()
    return _psycopg2_ok and bool(url) and "XXXXXXXXXX" not in url


def get_conn():
```

変更後:
```python
def _use_pg() -> bool:
    """Supabaseを使うかどうか（URLが正しく設定されている場合のみ）"""
    url = get_db_url()
    return _psycopg2_ok and bool(url) and "XXXXXXXXXX" not in url


def get_anthropic_key() -> str:
    """Claude APIキー: Streamlit Secrets優先、なければconfig.json"""
    try:
        return st.secrets["anthropic_api_key"]
    except Exception:
        return cfg.get("anthropic_api_key", "")


def get_conn():
```

- [ ] **Step 3: `get_store_totals()`を追加する**

`query_bumon_analysis()`関数の末尾（`return pd.concat([df, total], ignore_index=True)`）の直後、`make_bumon_excel()`関数の直前に追記する。

変更前:
```python
    total = pd.DataFrame([{
        "カテゴリー": "合計",
        "売数": total_売数,
        "売上": total_売上,
        "荒利": total_荒利,
        "SKU数": df["SKU数"].sum(),
        "荒利率": total_荒利 / total_売上 if total_売上 > 0 else None,
        "単価":   total_売上 / total_売数 if total_売数 > 0 else None,
        "1SKU当売数": None, "1SKU当売上": None, "1SKU当荒利": None,
        "売上順位": None, "荒利率順位": None,
    }])
    return pd.concat([df, total], ignore_index=True)


def make_bumon_excel(df: pd.DataFrame, store_label: str, start: str, end: str) -> bytes | None:
```

変更後:
```python
    total = pd.DataFrame([{
        "カテゴリー": "合計",
        "売数": total_売数,
        "売上": total_売上,
        "荒利": total_荒利,
        "SKU数": df["SKU数"].sum(),
        "荒利率": total_荒利 / total_売上 if total_売上 > 0 else None,
        "単価":   total_売上 / total_売数 if total_売数 > 0 else None,
        "1SKU当売数": None, "1SKU当売上": None, "1SKU当荒利": None,
        "売上順位": None, "荒利率順位": None,
    }])
    return pd.concat([df, total], ignore_index=True)


def get_store_totals(start: str, end: str, store_db: str) -> dict:
    """指定期間・店舗の売上・荒利・点数・客数の合計を返す"""
    sql = f"""
        SELECT
            COALESCE(SUM(sales_amount), 0)    AS sales,
            COALESCE(SUM(gross_profit), 0)    AS profit,
            COALESCE(SUM(sales_qty), 0)       AS qty,
            COALESCE(SUM(sales_customers), 0) AS customers
        FROM sales
        WHERE pos_date BETWEEN {_ph(1)} AND {_ph(1)} AND store_name = {_ph(1)}
    """
    try:
        con = get_conn()
        cur = con.cursor()
        cur.execute(_fix(sql), [start, end, store_db])
        row = cur.fetchone()
        cur.close()
        con.close()
    except Exception:
        row = (0, 0, 0, 0)
    sales, profit, qty, customers = row
    return {
        "sales": float(sales or 0),
        "profit": float(profit or 0),
        "qty": float(qty or 0),
        "customers": float(customers or 0),
    }


def make_bumon_excel(df: pd.DataFrame, store_label: str, start: str, end: str) -> bytes | None:
```

- [ ] **Step 4: 構文エラーがないことを確認する**

Run: `cd 売上管理/pos_system && python -m py_compile dashboard.py`
Expected: 何も出力されず終了コード0

- [ ] **Step 5: 手動でロジックを確認する**

一時的なSQLiteデータベースを作って`get_store_totals`の集計が正しいことを確認する。

Run:
```bash
cd 売上管理/pos_system && python -c "
import sqlite3, tempfile, os, json

tmp = tempfile.mktemp(suffix='.db')
con = sqlite3.connect(tmp)
con.execute('''CREATE TABLE sales (pos_date TEXT, store_name TEXT, sales_amount REAL, gross_profit REAL, sales_qty REAL, sales_customers REAL)''')
con.execute(\"INSERT INTO sales VALUES ('2026-06-01', 'テスト店', 1000, 300, 10, 5)\")
con.execute(\"INSERT INTO sales VALUES ('2026-06-02', 'テスト店', 2000, 600, 20, 8)\")
con.execute(\"INSERT INTO sales VALUES ('2026-06-02', '他店', 9999, 9999, 99, 99)\")
con.commit()
con.close()

import dashboard
dashboard.cfg['db_path_sqlite'] = tmp
dashboard.cfg['db_url'] = ''

result = dashboard.get_store_totals('2026-06-01', '2026-06-30', 'テスト店')
print(result)
assert result == {'sales': 3000.0, 'profit': 900.0, 'qty': 30.0, 'customers': 13.0}, result
print('OK')
os.remove(tmp)
"
```
Expected: 出力の最後が `OK`（途中にStreamlitのbareモード警告が出るが無視してよい）

- [ ] **Step 6: commit**

```bash
git add "売上管理/pos_system/dashboard.py"
git commit -m "$(cat <<'EOF'
feat(pos_system): AI改善提案レポート用のDB集計・APIキー取得関数を追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: `dashboard.py` — サイドバーUI・実行処理・結果表示

**Files:**
- Modify: `売上管理/pos_system/dashboard.py`

**Interfaces:**
- Consumes: `get_prev_month_range`, `build_metrics_summary`（Task 2-3）, `call_ai_advice`, `make_advice_docx`, `_docx_ok`（Task 4-5）, `get_anthropic_key`, `get_store_totals`（Task 6）, 既存の`query_bumon_analysis`, `store_mapping`, `selected_display`, `start_date`, `end_date`, `date_mode`

- [ ] **Step 1: サイドバーに管理者専用区画を追加する**

`with st.sidebar:` ブロック内、`bumon_btn = st.button(...)` の直後に追記する。

変更前:
```python
    st.divider()
    extract_btn = st.button("🔍 抽出実行", use_container_width=True, type="primary")
    bumon_btn   = st.button("📊 部門別分析レポート", use_container_width=True)

# ─── 抽出処理 ────────────────────────────────────────────────────────────────
```

変更後:
```python
    st.divider()
    extract_btn = st.button("🔍 抽出実行", use_container_width=True, type="primary")
    bumon_btn   = st.button("📊 部門別分析レポート", use_container_width=True)

    # ⑥ AI改善提案レポート（管理者専用）
    ai_advice_btn = False
    if st.session_state.get("is_admin"):
        st.divider()
        st.subheader("⑥ AI改善提案レポート（管理者専用）")
        if date_mode == "月選択":
            st.caption("⚠️ Claude APIの利用料金が発生します。")
            ai_agree = st.checkbox("料金が発生することに同意して実行する", key="ai_agree")
            st.caption(f"選択中の{len(selected_display)}店舗を分析します。")
            ai_advice_btn = st.button(
                "🤖 AI改善提案レポート",
                use_container_width=True,
                disabled=not ai_agree,
            )
        else:
            st.caption("「月選択」モードのときのみ利用できます。")

# ─── 抽出処理 ────────────────────────────────────────────────────────────────
```

- [ ] **Step 2: 実行処理を追加する**

`if bumon_btn:` ブロックの終わり（`st.session_state["bumon_meta"] = {...}`の閉じ括弧の直後）、`if not extract_btn and ...` の直前に追記する。

変更前:
```python
        else:
            st.session_state["bumon_result"] = df_bumon
            st.session_state["bumon_meta"] = {
                "stores": selected_display,
                "start": str(start_date),
                "end": str(end_date),
            }

if not extract_btn and "df_result" not in st.session_state and "bumon_result" not in st.session_state:
    st.info("👈 左のサイドバーで条件を設定して「抽出実行」または「部門別分析レポート」ボタンを押してください。")
    st.stop()
```

変更後:
```python
        else:
            st.session_state["bumon_result"] = df_bumon
            st.session_state["bumon_meta"] = {
                "stores": selected_display,
                "start": str(start_date),
                "end": str(end_date),
            }

if ai_advice_btn:
    if not selected_display:
        st.warning("店舗を1つ以上選択してください。")
    else:
        prev_range = get_prev_month_range(start_date, end_date)
        if prev_range is None:
            st.warning("前月データと比較できない期間です。「月選択」モードで単一の月を選んでください。")
        else:
            prev_start, prev_end = prev_range
            period_label = f"{start_date.year}年{start_date.month}月"
            api_key = get_anthropic_key()
            results = {}
            progress = st.progress(0.0)
            for i, display_name in enumerate(selected_display):
                store_db = store_mapping[display_name]
                cur_totals = get_store_totals(str(start_date), str(end_date), store_db)
                prev_totals = get_store_totals(str(prev_start), str(prev_end), store_db)
                cur_bumon = query_bumon_analysis(str(start_date), str(end_date), [store_db])
                prev_bumon = query_bumon_analysis(str(prev_start), str(prev_end), [store_db])
                metrics_text = build_metrics_summary(
                    display_name, period_label, cur_totals, prev_totals, cur_bumon, prev_bumon
                )
                results[display_name] = call_ai_advice(display_name, period_label, metrics_text, api_key)
                progress.progress((i + 1) / len(selected_display))
            st.session_state["ai_advice_result"] = results
            st.session_state["ai_advice_meta"] = {"period_label": period_label}

if (
    not extract_btn
    and "df_result" not in st.session_state
    and "bumon_result" not in st.session_state
    and "ai_advice_result" not in st.session_state
):
    st.info("👈 左のサイドバーで条件を設定して「抽出実行」または「部門別分析レポート」ボタンを押してください。")
    st.stop()
```

- [ ] **Step 3: 結果表示を追加する**

部門別分析レポートの表示ブロック末尾（`st.warning("openpyxl がインストールされていません...")`の直後）、管理者アクセスログのコメントの直前に追記する。

変更前:
```python
    else:
        st.warning("openpyxl がインストールされていません。`pip install openpyxl` を実行してください。")

# ─── 管理者：アクセスログ ─────────────────────────────────────────────────────
```

変更後:
```python
    else:
        st.warning("openpyxl がインストールされていません。`pip install openpyxl` を実行してください。")

# ─── AI改善提案レポート ─────────────────────────────────────────────────────
if "ai_advice_result" in st.session_state:
    ai_results = st.session_state["ai_advice_result"]
    ai_period_label = st.session_state["ai_advice_meta"]["period_label"]
    st.divider()
    st.subheader(f"🤖 AI改善提案レポート　{ai_period_label}")

    for store_label, advice_text in ai_results.items():
        with st.expander(store_label, expanded=False):
            st.markdown(advice_text)

    if _docx_ok:
        docx_bytes = make_advice_docx(ai_results, ai_period_label)
        if docx_bytes:
            st.download_button(
                label="📥 Wordダウンロード",
                data=docx_bytes,
                file_name=f"AI改善提案レポート_{ai_period_label}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
    else:
        st.warning("python-docx がインストールされていません。`pip install python-docx` を実行してください。")

# ─── 管理者：アクセスログ ─────────────────────────────────────────────────────
```

- [ ] **Step 4: 構文エラーがないことを確認する**

Run: `cd 売上管理/pos_system && python -m py_compile dashboard.py`
Expected: 何も出力されず終了コード0

- [ ] **Step 5: ローカルでダッシュボードを起動して手動確認する**

Run: `cd 売上管理/pos_system && streamlit run dashboard.py`

確認項目:
1. パスワード欄に管理者パスワード（`config.json`の`admin_password`または`dashboard_password`。Streamlit Secrets運用の場合は`st.secrets`側）を入力してログインできる
2. 日付モードを「月選択」にすると、サイドバーに「⑥ AI改善提案レポート（管理者専用）」が表示される
3. 日付モードを「日付範囲」や「月範囲」にすると、「「月選択」モードのときのみ利用できます。」という注意書きに切り替わる
4. 「料金が発生することに同意して実行する」にチェックを入れるまで「🤖 AI改善提案レポート」ボタンが押せない
5. データが存在する月・店舗（1〜2店舗）を選んでチェック→ボタン押下し、進捗バーが進んだ後、店舗ごとの開閉パネルに「■現状分析」「■改善施策」を含む文章が表示される
6. 「📥 Wordダウンロード」ボタンでファイルがダウンロードでき、開くと店舗名・生成文が含まれている
7. 通常ユーザー（管理者以外）のパスワードでログインした場合、「⑥ AI改善提案レポート」区画自体が表示されない

Expected: 上記すべてが期待通りに動作する。`config.json`の`anthropic_api_key`が未設定またはプレースホルダーのままの場合は、各店舗パネルに「⚠️ 生成に失敗しました（Anthropic APIキーが設定されていません...）」が表示されることも確認する

- [ ] **Step 6: commit**

```bash
git add "売上管理/pos_system/dashboard.py"
git commit -m "$(cat <<'EOF'
feat(pos_system): AI改善提案レポートのUI・実行処理・結果表示を追加

管理者専用・月選択モード限定・課金同意チェック付きで、店舗ごとに
Claude APIへ数値サマリーを渡し、改善提案を生成して画面表示・Word
ダウンロードできるようにした。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: デプロイ準備（Streamlit Cloud）

**Files:**
- なし（既存メモリ「ダッシュボードのデプロイ」の手順に従う）

**Interfaces:**
- Consumes: Task 1〜7の全変更

- [ ] **Step 1: GitHubへプッシュする**

Run: `git push`
Expected: リモートに全コミットが反映される（Streamlit Cloudはpushがないと更新されないため必須）

- [ ] **Step 2: Streamlit CloudのSecretsに`anthropic_api_key`を追加する**

Streamlit CloudのアプリのSettings → Secretsで、既存の`password`/`admin_password`/`[database]`に加えて`anthropic_api_key = "実際のAPIキー"`を追記して保存する（画面操作のためユーザー自身に依頼する）。

- [ ] **Step 3: requirements.txtの反映を確認する**

Streamlit Cloud側で再デプロイ後、アプリログに`anthropic`・`python-docx`のインストールエラーが出ていないことを確認する（ユーザー確認）。
