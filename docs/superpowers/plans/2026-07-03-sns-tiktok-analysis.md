# SNS（TikTok）投稿分析・企画ツール Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TikTok上の駄菓子・お菓子関連の人気投稿をハッシュタグ・キーワード検索で自動収集し、傾向分析とClaude APIによる投稿企画案をExcelレポートとして出力する、手動実行のツールを `SNS/` フォルダーに構築する。

**Architecture:** `SNS/`フォルダー内に責務ごとのモジュール（scraper / analyzer / planner / report）を配置し、`run.py`が順番に呼び出すパイプライン構成にする。各モジュールはCSV/dict/JSONなどのシンプルなデータでやり取りし、単体でテストできるようにする。

**Tech Stack:** Python 3.12, Selenium（Edge, ヘッドレス）, openpyxl, anthropic（Claude API）, pytest

## Global Constraints

- 対象SNSはTikTokのみ（Instagram/X/LINEは対象外）
- 検索キーワード・APIキー・取得件数などの設定値はすべて `SNS/config.json` に集約し、コードにハードコードしない（CLAUDE.mdルール）
- `SNS/config.json` は認証情報を含むため `.gitignore` 済み（ルートの`.gitignore`参照）
- 実行は手動のみ（`python run.py`）。定期実行の自動化は本計画のスコープ外
- コード内コメント・ログメッセージはすべて日本語（CLAUDE.mdルール）
- 出力レポートはExcelファイル1つに「傾向データ」シートと「投稿企画案」シートをまとめる
- 各タスク完了ごとに `git add` + `git commit` する

---

## ファイル構成

```
SNS/
├── config.json              # 検索キーワード・APIキー等の設定（gitignore対象）
├── .gitignore                # config.json / data/ を除外
├── requirements.txt          # selenium, openpyxl, anthropic, pytest
├── scraper.py                # TikTok検索結果の収集
├── test_scraper.py           # scraperの純粋関数のテスト
├── analyzer.py                # 収集データの集計
├── test_analyzer.py           # analyzerのテスト
├── planner.py                 # Claude APIで企画案を生成
├── test_planner.py            # plannerのテスト（API呼び出しはモック）
├── report.py                  # Excelレポート出力
├── test_report.py             # reportのテスト
├── run.py                     # エントリーポイント（手動実行）
└── data/                      # 実行時に自動生成（gitignore対象）
    ├── raw_YYYYMMDD.csv
    └── reports/YYYYMMDD.xlsx
```

**依存関係の向き:** `run.py` → `scraper.py` / `analyzer.py` / `planner.py` / `report.py`。モジュール間の相互依存はなし（`analyzer.py`が作る`summary`辞書を`planner.py`と`report.py`が受け取る形）。

---

### Task 1: プロジェクト雛形と設定ファイル作成

**Files:**
- Create: `SNS/requirements.txt`
- Create: `SNS/config.json`
- Create: `SNS/.gitignore`

**Interfaces:**
- Produces: `SNS/config.json` のキー構成 — `keywords: list[str]`, `max_videos_per_keyword: int`, `wait_seconds_between_requests: int`, `headless: bool`, `anthropic_api_key: str`。以降の全タスクがこの構成に依存する。

- [ ] **Step 1: requirements.txtを作成する**

`SNS/requirements.txt`:
```
selenium
openpyxl
anthropic
pytest
```

- [ ] **Step 2: config.jsonを作成する**

`SNS/config.json`:
```json
{
  "keywords": ["駄菓子", "うまい棒", "お菓子 デパート"],
  "max_videos_per_keyword": 15,
  "wait_seconds_between_requests": 5,
  "headless": true,
  "anthropic_api_key": "ここにClaude APIキーを入力してください"
}
```

- [ ] **Step 3: SNS用の.gitignoreを作成する**

`SNS/.gitignore`:
```
config.json
data/
__pycache__/
*.pyc
```

- [ ] **Step 4: 依存パッケージをインストールして確認する**

Run: `pip install -r SNS/requirements.txt`
Expected: エラーなくインストール完了

- [ ] **Step 5: コミット**

```bash
git add SNS/requirements.txt SNS/config.json SNS/.gitignore
git commit -m "feat(SNS): プロジェクト雛形と設定ファイルを追加"
```

---

### Task 2: analyzer.py — 集計ロジック

**Files:**
- Create: `SNS/analyzer.py`
- Create: `SNS/test_analyzer.py`

**Interfaces:**
- Consumes: なし（`records: list[dict]` を直接受け取る。1レコードのキーは `url, keyword, caption, hashtags(list[str]), likes(int), views(int), comments(int), shares(int), posted_at(str)`）
- Produces:
  - `load_records(csv_path: str) -> list[dict]`
  - `top_hashtags(records: list[dict], top_n: int = 10) -> list[tuple[str, int]]`
  - `top_videos(records: list[dict], top_n: int = 5, by: str = "likes") -> list[dict]`
  - `summarize(records: list[dict], top_n: int = 10) -> dict`（キー: `video_count, top_hashtags, top_videos_by_likes, keywords`）— Task 4, 5がこの`summary`辞書を受け取る

- [ ] **Step 1: 失敗するテストを書く**

`SNS/test_analyzer.py`:
```python
from analyzer import top_hashtags, top_videos, summarize

SAMPLE_RECORDS = [
    {
        "url": "https://www.tiktok.com/@a/video/1",
        "keyword": "駄菓子",
        "caption": "うまい棒の食べ比べ",
        "hashtags": ["駄菓子", "うまい棒"],
        "likes": 100,
        "views": 1000,
        "comments": 5,
        "shares": 2,
        "posted_at": "2026-06-01",
    },
    {
        "url": "https://www.tiktok.com/@b/video/2",
        "keyword": "駄菓子",
        "caption": "駄菓子屋開封動画",
        "hashtags": ["駄菓子", "開封"],
        "likes": 300,
        "views": 5000,
        "comments": 20,
        "shares": 10,
        "posted_at": "2026-06-05",
    },
    {
        "url": "https://www.tiktok.com/@c/video/3",
        "keyword": "うまい棒",
        "caption": "うまい棒コンプリート",
        "hashtags": ["うまい棒"],
        "likes": 50,
        "views": 800,
        "comments": 1,
        "shares": 0,
        "posted_at": "2026-06-10",
    },
]


def test_top_hashtags_orders_by_count_descending():
    result = top_hashtags(SAMPLE_RECORDS, top_n=3)
    # Counter.most_commonは同数の場合、最初に出現した順（駄菓子→うまい棒）を保つ
    assert result == [("駄菓子", 2), ("うまい棒", 2), ("開封", 1)]


def test_top_videos_sorts_by_likes_descending():
    result = top_videos(SAMPLE_RECORDS, top_n=2, by="likes")
    assert [v["url"] for v in result] == [
        "https://www.tiktok.com/@b/video/2",
        "https://www.tiktok.com/@a/video/1",
    ]


def test_summarize_returns_expected_keys():
    summary = summarize(SAMPLE_RECORDS, top_n=5)
    assert summary["video_count"] == 3
    assert summary["keywords"] == ["うまい棒", "駄菓子"]
    assert summary["top_hashtags"][0] == ("駄菓子", 2)
    assert len(summary["top_videos_by_likes"]) == 3
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd SNS && python -m pytest test_analyzer.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'analyzer'`）

- [ ] **Step 3: 実装する**

`SNS/analyzer.py`:
```python
"""投稿データの集計ロジック。"""
import csv
from collections import Counter


def load_records(csv_path):
    """CSVファイルから投稿データを読み込み、dictのリストとして返す。"""
    records = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["hashtags"] = row["hashtags"].split(";") if row["hashtags"] else []
            row["likes"] = int(row["likes"])
            row["views"] = int(row["views"])
            row["comments"] = int(row["comments"])
            row["shares"] = int(row["shares"])
            records.append(row)
    return records


def top_hashtags(records, top_n=10):
    """出現回数が多いハッシュタグを多い順に返す。"""
    counter = Counter()
    for record in records:
        counter.update(record["hashtags"])
    return counter.most_common(top_n)


def top_videos(records, top_n=5, by="likes"):
    """指定した指標（likes/views/comments/shares）で上位の投稿を返す。"""
    return sorted(records, key=lambda r: r[by], reverse=True)[:top_n]


def summarize(records, top_n=10):
    """傾向データをまとめて辞書で返す。"""
    return {
        "video_count": len(records),
        "top_hashtags": top_hashtags(records, top_n),
        "top_videos_by_likes": top_videos(records, 5, "likes"),
        "keywords": sorted({r["keyword"] for r in records}),
    }
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd SNS && python -m pytest test_analyzer.py -v`
Expected: PASS（3件とも成功）

- [ ] **Step 5: コミット**

```bash
git add SNS/analyzer.py SNS/test_analyzer.py
git commit -m "feat(SNS): analyzer.pyで投稿データの集計ロジックを追加"
```

---

### Task 3: report.py — Excelレポート出力

**Files:**
- Create: `SNS/report.py`
- Create: `SNS/test_report.py`

**Interfaces:**
- Consumes: Task 2の`summarize()`が返す`summary`辞書、`plan_ideas: list[str]`（Task 4で生成）
- Produces: `create_report(summary: dict, plan_ideas: list[str], output_path: str) -> None`

- [ ] **Step 1: 失敗するテストを書く**

`SNS/test_report.py`:
```python
from openpyxl import load_workbook
from report import create_report


def test_create_report_writes_trend_and_plan_sheets(tmp_path):
    summary = {
        "video_count": 2,
        "top_hashtags": [("駄菓子", 2), ("うまい棒", 1)],
        "top_videos_by_likes": [
            {
                "caption": "駄菓子屋開封動画",
                "likes": 300,
                "url": "https://www.tiktok.com/@b/video/2",
            },
        ],
    }
    plan_ideas = ["うまい棒の食べ比べ動画を作る"]
    output_path = tmp_path / "report.xlsx"

    create_report(summary, plan_ideas, str(output_path))

    wb = load_workbook(output_path)
    assert wb.sheetnames == ["傾向データ", "投稿企画案"]

    trend_sheet = wb["傾向データ"]
    assert trend_sheet["A1"].value == "集計投稿数"
    assert trend_sheet["B1"].value == 2

    plan_sheet = wb["投稿企画案"]
    assert plan_sheet["A2"].value == "うまい棒の食べ比べ動画を作る"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd SNS && python -m pytest test_report.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'report'`）

- [ ] **Step 3: 実装する**

`SNS/report.py`:
```python
"""集計結果と企画案をExcelファイルに出力する。"""
from openpyxl import Workbook


def create_report(summary, plan_ideas, output_path):
    """傾向データと投稿企画案をExcel1ファイル（2シート）にまとめて出力する。"""
    wb = Workbook()

    trend_sheet = wb.active
    trend_sheet.title = "傾向データ"
    trend_sheet.append(["集計投稿数", summary["video_count"]])
    trend_sheet.append([])
    trend_sheet.append(["人気ハッシュタグ", "件数"])
    for tag, count in summary["top_hashtags"]:
        trend_sheet.append([tag, count])

    trend_sheet.append([])
    trend_sheet.append(["いいね数上位の投稿", "いいね数", "URL"])
    for video in summary["top_videos_by_likes"]:
        trend_sheet.append([video["caption"], video["likes"], video["url"]])

    plan_sheet = wb.create_sheet("投稿企画案")
    plan_sheet.append(["企画案"])
    for idea in plan_ideas:
        plan_sheet.append([idea])

    wb.save(output_path)
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd SNS && python -m pytest test_report.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add SNS/report.py SNS/test_report.py
git commit -m "feat(SNS): report.pyでExcelレポート出力を追加"
```

---

### Task 4: planner.py — Claude APIによる投稿企画案の生成

**Files:**
- Create: `SNS/planner.py`
- Create: `SNS/test_planner.py`

**Interfaces:**
- Consumes: Task 2の`summarize()`が返す`summary`辞書
- Produces:
  - `build_prompt(summary: dict) -> str`
  - `generate_plan_ideas(summary: dict, api_key: str, client=None) -> list[str]`（`client`は主にテスト用の差し替え口。省略時は`anthropic.Anthropic(api_key=api_key)`を使う）— Task 3の`create_report()`と Task 6の`run.py`がこの戻り値を使う

- [ ] **Step 1: 失敗するテストを書く**

`SNS/test_planner.py`:
```python
from unittest.mock import MagicMock
from planner import build_prompt, generate_plan_ideas


def test_build_prompt_includes_hashtags_and_captions():
    summary = {
        "top_hashtags": [("駄菓子", 2)],
        "top_videos_by_likes": [{"caption": "駄菓子屋開封動画", "likes": 300}],
    }
    prompt = build_prompt(summary)
    assert "#駄菓子（2件）" in prompt
    assert "駄菓子屋開封動画（いいね300件）" in prompt


def test_generate_plan_ideas_parses_response_lines():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="- 企画案1\n- 企画案2")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    summary = {"top_hashtags": [], "top_videos_by_likes": []}
    result = generate_plan_ideas(summary, api_key="dummy", client=fake_client)

    assert result == ["企画案1", "企画案2"]


def test_generate_plan_ideas_returns_empty_list_on_error():
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("APIエラー")

    summary = {"top_hashtags": [], "top_videos_by_likes": []}
    result = generate_plan_ideas(summary, api_key="dummy", client=fake_client)

    assert result == []
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd SNS && python -m pytest test_planner.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'planner'`）

- [ ] **Step 3: 実装する**

`SNS/planner.py`:
```python
"""傾向データから投稿企画案を生成する。"""
import anthropic

CLAUDE_MODEL = "claude-sonnet-5"


def build_prompt(summary):
    """傾向データからClaude APIに渡すプロンプト文を作る。"""
    hashtag_lines = "\n".join(
        f"- #{tag}（{count}件）" for tag, count in summary["top_hashtags"]
    )
    caption_lines = "\n".join(
        f"- {v['caption']}（いいね{v['likes']}件）"
        for v in summary["top_videos_by_likes"]
    )
    return (
        "あなたは駄菓子店のSNS担当者向けにアドバイスするマーケティング担当です。\n"
        "以下はTikTokで人気の駄菓子関連投稿の傾向データです。\n\n"
        f"よく使われるハッシュタグ:\n{hashtag_lines}\n\n"
        f"反応が良かった投稿:\n{caption_lines}\n\n"
        "この傾向を踏まえて、駄菓子店が撮影できる具体的な投稿企画案を3つ、"
        "箇条書きで日本語で提案してください。"
    )


def generate_plan_ideas(summary, api_key, client=None):
    """Claude APIを使って投稿企画案を生成する。失敗時は空リストを返す。"""
    if client is None:
        client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt(summary)
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        return [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    except Exception as error:
        print(f"企画案の生成に失敗しました: {error}")
        return []
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd SNS && python -m pytest test_planner.py -v`
Expected: PASS（3件とも成功）

- [ ] **Step 5: コミット**

```bash
git add SNS/planner.py SNS/test_planner.py
git commit -m "feat(SNS): planner.pyでClaude APIによる企画案生成を追加"
```

---

### Task 5: scraper.py — TikTok検索結果の収集

**注意:** この機能はTikTok内部のページ構造（埋め込みJSON）に依存しており、TikTok側の仕様変更で動かなくなる可能性がある（設計書の「既知の制約・リスク」参照）。純粋関数部分は自動テストするが、実際にTikTokから取得できるかは最後に手動で確認し、構造が異なっていた場合は`extract_items_from_html`と`parse_item`のキー参照を実際のページに合わせて調整すること。

**Files:**
- Create: `SNS/scraper.py`
- Create: `SNS/test_scraper.py`

**Interfaces:**
- Consumes: `config`辞書（Task 1で定義した構成）
- Produces:
  - `extract_hashtags(caption: str) -> list[str]`
  - `extract_items_from_html(html: str) -> list[dict]`
  - `parse_item(raw_item: dict, keyword: str) -> dict`（Task 2の`records`と同じキー構成を返す）
  - `collect_all(config: dict) -> list[dict]`
  - `save_csv(records: list[dict], csv_path: str) -> None`

- [ ] **Step 1: 失敗するテストを書く（純粋関数部分）**

`SNS/test_scraper.py`:
```python
import json
from scraper import extract_hashtags, extract_items_from_html, parse_item


def test_extract_hashtags_finds_all_tags():
    caption = "うまい棒紹介 #駄菓子 #うまい棒 楽しい"
    assert extract_hashtags(caption) == ["駄菓子", "うまい棒"]


def test_extract_hashtags_returns_empty_list_when_no_tags():
    assert extract_hashtags("ハッシュタグなしのキャプション") == []


def test_extract_items_from_html_parses_embedded_json():
    payload = {
        "__DEFAULT_SCOPE__": {
            "webapp.search-detail": {
                "searchResult": {"itemList": [{"item": {"id": "123"}}]}
            }
        }
    }
    html = (
        '<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">'
        f"{json.dumps(payload)}</script></html>"
    )
    items = extract_items_from_html(html)
    assert items == [{"item": {"id": "123"}}]


def test_extract_items_from_html_returns_empty_list_when_missing():
    assert extract_items_from_html("<html></html>") == []


def test_parse_item_converts_raw_item_to_record():
    raw_item = {
        "item": {
            "id": "123",
            "desc": "駄菓子紹介 #駄菓子",
            "createTime": 1750000000,
            "author": {"uniqueId": "yoshiya_tenri"},
            "stats": {
                "diggCount": 10,
                "playCount": 100,
                "commentCount": 2,
                "shareCount": 1,
            },
        }
    }
    record = parse_item(raw_item, keyword="駄菓子")
    assert record["url"] == "https://www.tiktok.com/@yoshiya_tenri/video/123"
    assert record["hashtags"] == ["駄菓子"]
    assert record["likes"] == 10
    assert record["views"] == 100
    assert record["comments"] == 2
    assert record["shares"] == 1
    assert record["keyword"] == "駄菓子"
    assert record["posted_at"] == "2025-06-15"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd SNS && python -m pytest test_scraper.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'scraper'`）

- [ ] **Step 3: 実装する**

`SNS/scraper.py`:
```python
"""TikTokのハッシュタグ・キーワード検索結果から投稿データを収集する。"""
import csv
import json
import re
import time
from datetime import datetime, timezone

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SEARCH_URL = "https://www.tiktok.com/search/video?q={keyword}"
STATE_SCRIPT_ID = "__UNIVERSAL_DATA_FOR_REHYDRATION__"


def build_driver(headless=True):
    """Edge用のSeleniumドライバーを作成する。"""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Edge(options=options)


def extract_hashtags(caption):
    """キャプション文字列からハッシュタグの一覧を抽出する。"""
    return re.findall(r"#(\S+)", caption)


def extract_items_from_html(html):
    """検索結果ページのHTMLから投稿データのリストを取り出す。

    TikTokはページ内の<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">タグに
    検索結果のJSONを埋め込んでいる。TikTok側の仕様変更でこの構造が変わった場合は
    実際のページのHTMLを確認してこの関数を修正すること。
    """
    match = re.search(
        rf'<script id="{STATE_SCRIPT_ID}"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if not match:
        return []
    data = json.loads(match.group(1))
    default_scope = data.get("__DEFAULT_SCOPE__", {})
    search_data = default_scope.get("webapp.search-detail", {})
    return search_data.get("searchResult", {}).get("itemList", [])


def parse_item(raw_item, keyword):
    """検索結果1件分の生データを、レポート用の形式に変換する。"""
    item = raw_item.get("item", raw_item)
    video_id = item.get("id", "")
    author = item.get("author", {}).get("uniqueId", "")
    stats = item.get("stats", {})
    caption = item.get("desc", "")
    create_time = item.get("createTime")
    posted_at = ""
    if create_time:
        posted_at = datetime.fromtimestamp(
            int(create_time), tz=timezone.utc
        ).strftime("%Y-%m-%d")

    return {
        "url": f"https://www.tiktok.com/@{author}/video/{video_id}",
        "keyword": keyword,
        "caption": caption,
        "hashtags": extract_hashtags(caption),
        "likes": int(stats.get("diggCount", 0)),
        "views": int(stats.get("playCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
        "shares": int(stats.get("shareCount", 0)),
        "posted_at": posted_at,
    }


def search_keyword(driver, keyword, max_videos):
    """1つのキーワードでTikTok検索を行い、投稿データのリストを返す。"""
    driver.get(SEARCH_URL.format(keyword=keyword))
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(3)  # ページ内JSONの読み込み待ち
    raw_items = extract_items_from_html(driver.page_source)
    return [parse_item(raw, keyword) for raw in raw_items[:max_videos]]


def collect_all(config):
    """設定ファイルのキーワード一覧すべてについて検索し、投稿データをまとめて返す。"""
    driver = build_driver(headless=config.get("headless", True))
    all_records = []
    try:
        for keyword in config["keywords"]:
            print(f"「{keyword}」を検索中...")
            try:
                records = search_keyword(
                    driver, keyword, config["max_videos_per_keyword"]
                )
                all_records.extend(records)
            except Exception as error:
                print(f"「{keyword}」の取得に失敗しました: {error}")
            time.sleep(config.get("wait_seconds_between_requests", 5))
    finally:
        driver.quit()
    return all_records


def save_csv(records, csv_path):
    """収集した投稿データをCSVファイルに保存する。"""
    fieldnames = [
        "url", "keyword", "caption", "hashtags",
        "likes", "views", "comments", "shares", "posted_at",
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["hashtags"] = ";".join(row["hashtags"])
            writer.writerow(row)
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd SNS && python -m pytest test_scraper.py -v`
Expected: PASS（5件とも成功）

- [ ] **Step 5: コミット**

```bash
git add SNS/scraper.py SNS/test_scraper.py
git commit -m "feat(SNS): scraper.pyでTikTok検索結果の収集ロジックを追加"
```

- [ ] **Step 6: 実際のTikTokに対して手動で動作確認する**

`config.json`の`keywords`を`["駄菓子"]`など1件だけにし、以下を対話的に実行して動作を確認する:

```python
import json
from scraper import collect_all, save_csv

with open("config.json", encoding="utf-8") as f:
    config = json.load(f)
config["keywords"] = ["駄菓子"]
config["max_videos_per_keyword"] = 5

records = collect_all(config)
print(f"{len(records)}件取得")
for r in records[:3]:
    print(r)
```

Expected: 1件以上のレコードが取得できる。0件の場合や例外が出る場合は、実際のページのHTML（`driver.page_source`）を確認し、`STATE_SCRIPT_ID`や`extract_items_from_html`内のキー名（`__DEFAULT_SCOPE__`, `webapp.search-detail`など）をブラウザの開発者ツールで見た実際の構造に合わせて修正する。修正した場合は再度Step 4のテストも通ることを確認してからコミットする。

---

### Task 6: run.py — エントリーポイントの結合

**Files:**
- Create: `SNS/run.py`

**Interfaces:**
- Consumes: `scraper.collect_all`, `scraper.save_csv`, `analyzer.load_records`, `analyzer.summarize`, `planner.generate_plan_ideas`, `report.create_report`（すべて既存タスクで実装済み）

- [ ] **Step 1: run.pyを実装する**

`SNS/run.py`:
```python
"""SNS投稿分析ツールのエントリーポイント。手動実行用。"""
import json
from datetime import date
from pathlib import Path

from scraper import collect_all, save_csv
from analyzer import load_records, summarize
from planner import generate_plan_ideas
from report import create_report

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = DATA_DIR / "reports"


def main():
    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    today = date.today().strftime("%Y%m%d")
    csv_path = DATA_DIR / f"raw_{today}.csv"
    report_path = REPORTS_DIR / f"{today}.xlsx"

    print("TikTokから投稿データを収集しています...")
    records = collect_all(config)
    save_csv(records, csv_path)
    print(f"{len(records)}件の投稿データを取得しました: {csv_path}")

    records = load_records(csv_path)
    summary = summarize(records)

    print("Claude APIで投稿企画案を生成しています...")
    plan_ideas = generate_plan_ideas(summary, config["anthropic_api_key"])

    create_report(summary, plan_ideas, str(report_path))
    print(f"レポートを出力しました: {report_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: config.jsonにClaude APIキーを設定する**

`SNS/config.json`の`anthropic_api_key`に実際のAPIキーを入力する（ユーザー自身の作業）。

- [ ] **Step 3: 実際に手動実行して動作確認する**

Run: `cd SNS && python run.py`
Expected: エラーなく完了し、`SNS/data/reports/YYYYMMDD.xlsx`が生成される。生成されたExcelファイルを開き、「傾向データ」シートと「投稿企画案」シートにそれらしい内容が入っていることを目視確認する。

- [ ] **Step 4: コミット**

```bash
git add SNS/run.py
git commit -m "feat(SNS): run.pyでパイプライン全体を結合"
```

---

## 完了確認

- [ ] `cd SNS && python -m pytest -v` で全テストがPASSする
- [ ] `python run.py` を実行し、Excelレポートが生成され、内容が実用的である
- [ ] `SNS/config.json`と`SNS/data/`がGit管理対象外になっている（`git status`で確認）
