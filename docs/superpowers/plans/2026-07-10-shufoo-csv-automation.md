# SHUFOO掲載用CSV・画像ZIP作成の自動化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 対話形式のPythonスクリプトで、SHUFOO掲載用CSV（店舗ごとの登録行）と参照画像のZIPを生成し、前回分を手作業でコピー・書き換えている現状の運用を置き換える。

**Architecture:** `日次業務/shufoo/config.json` にパターン（お買い得チラシ／やすい！）ごとの店舗マスターを保持し、`make_shufoo_csv.py` の純粋関数群（日付計算・CSV行組み立て・画像チェック・ZIP生成）がロジックを担う。`input()` を使う対話部分（`main()`）はこれらの関数を呼び出すだけの薄いラッパーとし、ロジックはユニットテストで、対話部分は手動実行で検証する。

**Tech Stack:** Python 3.12（標準ライブラリのみ: `json`, `csv`, `zipfile`, `datetime`, `pathlib`）、pytest

## Global Constraints

- CSVの文字コードはcp932（Shift-JIS系）で書き出す（SHUFOOの実例フォーマットに合わせる）
- コメント・ログ・print文のメッセージはすべて日本語で書く
- 設定値（店舗マスター、出力ファイル名）はconfig.jsonに集約する
- 対応パターンは「お買い得チラシ」「やすい！」の2つで固定（将来のパターン追加は対象外）
- 掲載開始日時 = 「開始日の前日 19:00」、掲載終了日時 = 「終了日 15:00」で全パターン共通固定
- ファイル出力先は `日次業務/shufoo/` フォルダ、CSV・ZIPともに毎回同じファイル名で上書き保存

---

## ファイル構成

| ファイル | 役割 |
|---|---|
| `日次業務/shufoo/config.json` | パターンごとの店舗マスター（店舗ID・店舗名・チラシ入稿ID）と出力ファイル名 |
| `日次業務/shufoo/make_shufoo_csv.py` | CSV/ZIP生成ロジック＋対話形式のCLI（`main()`） |
| `日次業務/shufoo/test_make_shufoo_csv.py` | ロジック部分のユニットテスト |

---

### Task 1: config.jsonの作成とload_config関数

**Files:**
- Create: `日次業務/shufoo/config.json`
- Create: `日次業務/shufoo/make_shufoo_csv.py`
- Test: `日次業務/shufoo/test_make_shufoo_csv.py`

**Interfaces:**
- Consumes: なし（最初のタスク）
- Produces: `load_config(config_path) -> dict`（`{"patterns": {パターンキー: {"label", "csv_filename", "zip_filename", "stores": [{"entry_id", "store_id", "store_name"}, ...]}}}` の構造を返す）

- [ ] **Step 1: テストディレクトリを確認する**

Run: `ls "日次業務/shufoo"`
Expected: 既存の `tirasi.csv`, `tirasiyasui.csv`, `7.10-11.zip`, `yasui7.10-12.zip` が表示される

- [ ] **Step 2: 失敗するテストを書く**

`日次業務/shufoo/test_make_shufoo_csv.py` を新規作成:

```python
import json

from make_shufoo_csv import load_config


def test_load_config_reads_patterns_and_stores(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({
            "patterns": {
                "otoku": {
                    "label": "お買い得チラシ",
                    "csv_filename": "tirasi.csv",
                    "zip_filename": "tirasi_images.zip",
                    "stores": [
                        {"entry_id": "20250221", "store_id": "881827", "store_name": "テスト店"}
                    ],
                }
            }
        }),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["patterns"]["otoku"]["label"] == "お買い得チラシ"
    assert config["patterns"]["otoku"]["csv_filename"] == "tirasi.csv"
    assert config["patterns"]["otoku"]["stores"][0]["store_id"] == "881827"
```

- [ ] **Step 3: テストが失敗することを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'make_shufoo_csv'` または `ImportError`）

- [ ] **Step 4: 最小限の実装を書く**

`日次業務/shufoo/make_shufoo_csv.py` を新規作成:

```python
"""SHUFOO掲載用CSVと画像ZIPを対話形式で生成する。"""
import json


def load_config(config_path):
    """config.jsonを読み込む。"""
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 5: テストが通ることを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: PASS

- [ ] **Step 6: 実データのconfig.jsonを作成する**

`日次業務/shufoo/config.json` を新規作成（今回提供された2つのCSVの店舗一覧をそのまま登録する）:

```json
{
  "patterns": {
    "otoku": {
      "label": "お買い得チラシ",
      "csv_filename": "tirasi.csv",
      "zip_filename": "tirasi_images.zip",
      "stores": [
        {"entry_id": "20250221", "store_id": "881827", "store_name": "お菓子のデパートよしや　ユニバーサルシティ駅前店"},
        {"entry_id": "20250221", "store_id": "881828", "store_name": "お菓子のデパートよしや　春日出店"},
        {"entry_id": "20250221", "store_id": "881829", "store_name": "お菓子のデパートよしや　九条営業所"},
        {"entry_id": "20250221", "store_id": "881834", "store_name": "お菓子のデパートよしや　天満営業所"},
        {"entry_id": "20250221", "store_id": "881842", "store_name": "お菓子のデパートよしや　心斎橋営業所"},
        {"entry_id": "20250221", "store_id": "881843", "store_name": "お菓子のデパートよしや　南千里営業所"},
        {"entry_id": "20250221", "store_id": "881845", "store_name": "お菓子のデパートよしや　金剛営業所"},
        {"entry_id": "20250221", "store_id": "881848", "store_name": "お菓子のデパートよしや　河内長野営業所"},
        {"entry_id": "20250221", "store_id": "881852", "store_name": "お菓子のデパートよしや　四条河原町営業所"},
        {"entry_id": "20250221", "store_id": "881853", "store_name": "お菓子のデパートよしや　出町営業所"},
        {"entry_id": "20250221", "store_id": "881855", "store_name": "お菓子のデパートよしや　アステ川西店"},
        {"entry_id": "20250221", "store_id": "881858", "store_name": "お菓子のデパートよしや　尼崎営業所"},
        {"entry_id": "20250221", "store_id": "881859", "store_name": "お菓子のデパートよしや　神田営業所"},
        {"entry_id": "20250221", "store_id": "881860", "store_name": "お菓子のデパートよしや　元町営業所"},
        {"entry_id": "20250221", "store_id": "881861", "store_name": "お菓子のデパートよしや　伊丹営業所"},
        {"entry_id": "20250221", "store_id": "881864", "store_name": "お菓子のデパートよしや　とれとれ市場店"}
      ]
    },
    "yasui": {
      "label": "やすい！",
      "csv_filename": "tirasiyasui.csv",
      "zip_filename": "tirasiyasui_images.zip",
      "stores": [
        {"entry_id": "20251009", "store_id": "881840", "store_name": "やすい！桃谷店"},
        {"entry_id": "20251009", "store_id": "881857", "store_name": "やすい！姫路美幸通り店"},
        {"entry_id": "20251009", "store_id": "881838", "store_name": "やすい！京橋店"},
        {"entry_id": "20251009", "store_id": "881835", "store_name": "やすい！淡路店"},
        {"entry_id": "20251009", "store_id": "881832", "store_name": "やすい！泉尾店"},
        {"entry_id": "20251009", "store_id": "881831", "store_name": "やすい！塚本店"},
        {"entry_id": "20251010", "store_id": "881830", "store_name": "やすい！　四貫島店"},
        {"entry_id": "20251011", "store_id": "881847", "store_name": "お菓子のデパートよしや　布施営業所"},
        {"entry_id": "20251010", "store_id": "881851", "store_name": "お菓子のデパートよしや　伏見営業所"},
        {"entry_id": "20251018", "store_id": "881863", "store_name": "お菓子のデパートよしや　天理店"},
        {"entry_id": "20251019", "store_id": "907938", "store_name": "やすい！　空堀店"},
        {"entry_id": "20251020", "store_id": "881865", "store_name": "お菓子のデパートよしや　ミ・ナーラ店"},
        {"entry_id": "20251021", "store_id": "881837", "store_name": "お菓子のデパートよしや　三国営業所"}
      ]
    }
  }
}
```

- [ ] **Step 7: コミット**

```bash
git add "日次業務/shufoo/config.json" "日次業務/shufoo/make_shufoo_csv.py" "日次業務/shufoo/test_make_shufoo_csv.py"
git commit -m "feat(shufoo): config.jsonと店舗マスター読み込み関数を追加"
```

---

### Task 2: 日付処理（parse_date, compute_period, format_datetime）

**Files:**
- Modify: `日次業務/shufoo/make_shufoo_csv.py`
- Test: `日次業務/shufoo/test_make_shufoo_csv.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `parse_date(text: str, default_year: int) -> date`
  - `compute_period(start_date: date, end_date: date) -> tuple[datetime, datetime]`
  - `format_datetime(dt: datetime) -> str`（例: `"2026/7/9 19:00"`）

- [ ] **Step 1: 失敗するテストを書く**

`test_make_shufoo_csv.py` に追記:

```python
from datetime import date, datetime

from make_shufoo_csv import compute_period, format_datetime, parse_date


def test_parse_date_with_month_day_only_uses_default_year():
    result = parse_date("7/10", default_year=2026)
    assert result == date(2026, 7, 10)


def test_parse_date_with_full_year():
    result = parse_date("2026/7/10", default_year=2099)
    assert result == date(2026, 7, 10)


def test_parse_date_rejects_invalid_format():
    try:
        parse_date("2026-07-10", default_year=2026)
        assert False, "ValueErrorが発生するはず"
    except ValueError:
        pass


def test_compute_period_start_is_previous_day_19_00():
    start_dt, end_dt = compute_period(date(2026, 7, 10), date(2026, 7, 11))
    assert start_dt == datetime(2026, 7, 9, 19, 0)
    assert end_dt == datetime(2026, 7, 11, 15, 0)


def test_compute_period_handles_year_boundary():
    start_dt, end_dt = compute_period(date(2027, 1, 1), date(2027, 1, 3))
    assert start_dt == datetime(2026, 12, 31, 19, 0)
    assert end_dt == datetime(2027, 1, 3, 15, 0)


def test_format_datetime_matches_shufoo_style():
    assert format_datetime(datetime(2026, 7, 9, 19, 0)) == "2026/7/9 19:00"
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: FAIL（`ImportError: cannot import name 'parse_date'` など）

- [ ] **Step 3: 実装する**

`make_shufoo_csv.py` の先頭のimportを更新し、関数を追加:

```python
from datetime import date, datetime, time, timedelta


def parse_date(text, default_year):
    """日付文字列（M/D または YYYY/M/D）をdateに変換する。"""
    parts = text.strip().split("/")
    if len(parts) == 2:
        month, day = int(parts[0]), int(parts[1])
        year = default_year
    elif len(parts) == 3:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        raise ValueError(f"日付の形式が正しくありません: {text}")
    return date(year, month, day)


def compute_period(start_date, end_date):
    """掲載開始日時（開始日の前日19:00）と掲載終了日時（終了日15:00）を計算する。"""
    start_dt = datetime.combine(start_date - timedelta(days=1), time(19, 0))
    end_dt = datetime.combine(end_date, time(15, 0))
    return start_dt, end_dt


def format_datetime(dt):
    """日時をCSV用の文字列（例: 2026/7/9 19:00）に変換する。"""
    return f"{dt.year}/{dt.month}/{dt.day} {dt.hour}:{dt.minute:02d}"
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: PASS（全7件）

- [ ] **Step 5: コミット**

```bash
git add "日次業務/shufoo/make_shufoo_csv.py" "日次業務/shufoo/test_make_shufoo_csv.py"
git commit -m "feat(shufoo): 掲載日時の計算・フォーマット関数を追加"
```

---

### Task 3: CSV行組み立て（resolve_image_filename, build_csv_rows）

**Files:**
- Modify: `日次業務/shufoo/make_shufoo_csv.py`
- Test: `日次業務/shufoo/test_make_shufoo_csv.py`

**Interfaces:**
- Consumes: `format_datetime(dt) -> str`（Task 2）
- Produces:
  - `CSV_HEADER: list[str]`（25列のヘッダー名）
  - `resolve_image_filename(store: dict, default_image: str, overrides: dict[str, str]) -> str`
  - `build_csv_rows(stores: list[dict], start_dt: datetime, end_dt: datetime, title: str, default_image: str, overrides: dict[str, str]) -> list[list[str]]`（各行は25要素のリスト。列7=1ページ目画像、列23="1"、列24="", 列25="N"）

- [ ] **Step 1: 失敗するテストを書く**

`test_make_shufoo_csv.py` に追記:

```python
from make_shufoo_csv import build_csv_rows, resolve_image_filename


def test_resolve_image_filename_uses_default_when_no_override():
    store = {"entry_id": "1", "store_id": "881827", "store_name": "テスト店"}
    assert resolve_image_filename(store, "default.JPG", {}) == "default.JPG"


def test_resolve_image_filename_uses_override_when_present():
    store = {"entry_id": "1", "store_id": "881863", "store_name": "天理店"}
    overrides = {"881863": "yasui_tenri.JPG"}
    assert resolve_image_filename(store, "yasui.JPG", overrides) == "yasui_tenri.JPG"


def test_build_csv_rows_produces_25_columns_per_store():
    stores = [
        {"entry_id": "20250221", "store_id": "881827", "store_name": "テスト店A"},
        {"entry_id": "20250221", "store_id": "881863", "store_name": "天理店"},
    ]
    start_dt = datetime(2026, 7, 9, 19, 0)
    end_dt = datetime(2026, 7, 11, 15, 0)
    overrides = {"881863": "special.JPG"}

    rows = build_csv_rows(stores, start_dt, end_dt, "テストタイトル", "default.JPG", overrides)

    assert len(rows) == 2
    assert len(rows[0]) == 25
    assert rows[0][:7] == [
        "20250221", "881827", "テスト店A",
        "2026/7/9 19:00", "2026/7/11 15:00", "テストタイトル", "default.JPG",
    ]
    assert rows[0][7:22] == [""] * 15
    assert rows[0][22:] == ["1", "", "N"]
    assert rows[1][6] == "special.JPG"
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: FAIL（`ImportError: cannot import name 'build_csv_rows'`）

- [ ] **Step 3: 実装する**

`make_shufoo_csv.py` に追加:

```python
CSV_HEADER = [
    "チラシ入稿ID", "Shufoo!店舗ID(必須)", "先方店舗名",
    "掲載開始日時(必須)", "掲載終了日時(必須)", "チラシタイトル(必須)",
    "チラシ画像ファイル（１ページ目）", "チラシ画像ファイル（２ページ目）",
    "チラシ画像ファイル（３ページ目）", "チラシ画像ファイル（４ページ目）",
    "チラシ画像ファイル（５ページ目）", "チラシ画像ファイル（６ページ目）",
    "チラシ画像ファイル（７ページ目）", "チラシ画像ファイル（８ページ目）",
    "チラシ画像ファイル（９ページ目）", "チラシ画像ファイル（１０ページ目）",
    "チラシ画像ファイル（１１ページ目）", "チラシ画像ファイル（１２ページ目）",
    "チラシ画像ファイル（１３ページ目）", "チラシ画像ファイル（１４ページ目）",
    "チラシ画像ファイル（１５ページ目）", "チラシ画像ファイル（１６ページ目）",
    "ページスタイル", "ページの開き方", "掲載期間表示有無",
]


def resolve_image_filename(store, default_image, overrides):
    """店舗ごとの画像ファイル名を決定する（例外指定があればそちらを優先）。"""
    return overrides.get(store["store_id"], default_image)


def build_csv_rows(stores, start_dt, end_dt, title, default_image, overrides):
    """店舗マスターと入力値から、CSVの各行（25要素のリスト）を組み立てる。"""
    start_text = format_datetime(start_dt)
    end_text = format_datetime(end_dt)
    rows = []
    for store in stores:
        image = resolve_image_filename(store, default_image, overrides)
        row = (
            [store["entry_id"], store["store_id"], store["store_name"],
             start_text, end_text, title, image]
            + [""] * 15
            + ["1", "", "N"]
        )
        rows.append(row)
    return rows
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: PASS（全10件）

- [ ] **Step 5: コミット**

```bash
git add "日次業務/shufoo/make_shufoo_csv.py" "日次業務/shufoo/test_make_shufoo_csv.py"
git commit -m "feat(shufoo): CSV行の組み立てロジックを追加"
```

---

### Task 4: CSV書き出しと使用画像収集（write_csv, collect_used_images）

**Files:**
- Modify: `日次業務/shufoo/make_shufoo_csv.py`
- Test: `日次業務/shufoo/test_make_shufoo_csv.py`

**Interfaces:**
- Consumes: `CSV_HEADER: list[str]`, `build_csv_rows(...) -> list[list[str]]`（Task 3）
- Produces:
  - `write_csv(rows: list[list[str]], csv_path: Path) -> None`（cp932でヘッダー＋行を書き出す）
  - `collect_used_images(rows: list[list[str]]) -> list[str]`（列7の画像ファイル名を重複除去して昇順ソートで返す）

- [ ] **Step 1: 失敗するテストを書く**

`test_make_shufoo_csv.py` に追記:

```python
from make_shufoo_csv import collect_used_images, write_csv


def test_write_csv_writes_header_and_rows_in_cp932(tmp_path):
    rows = [["20250221", "881827", "テスト店", "2026/7/9 19:00", "2026/7/11 15:00",
              "タイトル", "default.JPG"] + [""] * 15 + ["1", "", "N"]]
    csv_path = tmp_path / "output.csv"

    write_csv(rows, csv_path)

    text = csv_path.read_bytes().decode("cp932")
    assert "チラシ入稿ID" in text
    assert "テスト店" in text
    assert "default.JPG" in text


def test_collect_used_images_deduplicates_and_sorts():
    rows = [
        ["1", "881827", "店A", "s", "e", "t", "b.JPG"] + [""] * 15 + ["1", "", "N"],
        ["1", "881828", "店B", "s", "e", "t", "a.JPG"] + [""] * 15 + ["1", "", "N"],
        ["1", "881829", "店C", "s", "e", "t", "b.JPG"] + [""] * 15 + ["1", "", "N"],
    ]
    assert collect_used_images(rows) == ["a.JPG", "b.JPG"]
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: FAIL（`ImportError: cannot import name 'write_csv'`）

- [ ] **Step 3: 実装する**

`make_shufoo_csv.py` の先頭に`csv`のimportを追加し、関数を追加:

```python
import csv


def write_csv(rows, csv_path):
    """CSVをcp932エンコードで書き出す（既存ファイルは上書き）。"""
    with open(csv_path, "w", encoding="cp932", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)


def collect_used_images(rows):
    """CSVの各行から、1ページ目の画像ファイル名を重複除去して集める。"""
    return sorted({row[6] for row in rows if row[6]})
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: PASS（全12件）

- [ ] **Step 5: コミット**

```bash
git add "日次業務/shufoo/make_shufoo_csv.py" "日次業務/shufoo/test_make_shufoo_csv.py"
git commit -m "feat(shufoo): CSV書き出しと使用画像の重複除去を追加"
```

---

### Task 5: 画像存在チェックとZIP書き出し（check_images_exist, write_zip）

**Files:**
- Modify: `日次業務/shufoo/make_shufoo_csv.py`
- Test: `日次業務/shufoo/test_make_shufoo_csv.py`

**Interfaces:**
- Consumes: なし（`folder`は`pathlib.Path`、`image_filenames`は`list[str]`）
- Produces:
  - `check_images_exist(image_filenames: list[str], folder: Path) -> tuple[list[str], list[str]]`（`(存在するファイル一覧, 存在しないファイル一覧)`）
  - `write_zip(image_filenames: list[str], folder: Path, zip_path: Path) -> None`

- [ ] **Step 1: 失敗するテストを書く**

`test_make_shufoo_csv.py` に追記:

```python
import zipfile

from make_shufoo_csv import check_images_exist, write_zip


def test_check_images_exist_splits_existing_and_missing(tmp_path):
    (tmp_path / "a.JPG").write_bytes(b"dummy")

    existing, missing = check_images_exist(["a.JPG", "b.JPG"], tmp_path)

    assert existing == ["a.JPG"]
    assert missing == ["b.JPG"]


def test_write_zip_bundles_only_specified_images(tmp_path):
    (tmp_path / "a.JPG").write_bytes(b"image-a")
    (tmp_path / "b.JPG").write_bytes(b"image-b")
    zip_path = tmp_path / "out.zip"

    write_zip(["a.JPG"], tmp_path, zip_path)

    with zipfile.ZipFile(zip_path) as z:
        assert z.namelist() == ["a.JPG"]
        assert z.read("a.JPG") == b"image-a"
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: FAIL（`ImportError: cannot import name 'check_images_exist'`）

- [ ] **Step 3: 実装する**

`make_shufoo_csv.py` の先頭に`zipfile`のimportを追加し、関数を追加:

```python
import zipfile


def check_images_exist(image_filenames, folder):
    """画像フォルダ内に実在するかを確認し、(存在するファイル一覧, 存在しないファイル一覧)を返す。"""
    existing, missing = [], []
    for name in image_filenames:
        if (folder / name).exists():
            existing.append(name)
        else:
            missing.append(name)
    return existing, missing


def write_zip(image_filenames, folder, zip_path):
    """指定した画像ファイルをZIPにまとめる（既存ファイルは上書き）。"""
    with zipfile.ZipFile(zip_path, "w") as z:
        for name in image_filenames:
            z.write(folder / name, arcname=name)
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: PASS（全14件）

- [ ] **Step 5: コミット**

```bash
git add "日次業務/shufoo/make_shufoo_csv.py" "日次業務/shufoo/test_make_shufoo_csv.py"
git commit -m "feat(shufoo): 画像の実在チェックとZIP書き出しを追加"
```

---

### Task 6: 対話CLI（prompt_pattern, prompt_overrides, main）

**Files:**
- Modify: `日次業務/shufoo/make_shufoo_csv.py`

**Interfaces:**
- Consumes: `load_config`（Task 1）, `parse_date`, `compute_period`（Task 2）, `build_csv_rows`（Task 3）, `write_csv`, `collect_used_images`（Task 4）, `check_images_exist`, `write_zip`（Task 5）
- Produces: `prompt_pattern(config: dict) -> tuple[str, dict]`, `prompt_date(label: str, default_year: int) -> date`, `prompt_overrides(stores: list[dict]) -> dict[str, str]`, `main() -> None`

対話部分は`input()`に依存するためユニットテストの対象外とする（既存コードベースの`メール処理/mail_check.py`と同じ方針で、ロジック関数のみテストし、`main()`は手動実行で確認する）。

- [ ] **Step 1: 実装する**

`make_shufoo_csv.py` の先頭に`Path`のimportを追加し、末尾に追加:

```python
from pathlib import Path


def prompt_pattern(config):
    """パターンを選択させ、(pattern_key, pattern_config)を返す。"""
    keys = list(config["patterns"].keys())
    print("パターンを選択してください:")
    for i, key in enumerate(keys, start=1):
        print(f"{i}: {config['patterns'][key]['label']}")
    choice = int(input("番号を入力: "))
    key = keys[choice - 1]
    return key, config["patterns"][key]


def prompt_date(label, default_year):
    """日付の入力を受け付け、正しい形式になるまで再入力を促す。"""
    while True:
        text = input(f"{label}（例: 7/10）: ").strip()
        try:
            return parse_date(text, default_year)
        except ValueError as error:
            print(f"エラー: {error}")


def prompt_overrides(stores):
    """例外店舗（画像ファイル名が異なる店舗）の入力を受け付け、{store_id: filename}を返す。"""
    overrides = {}
    print("画像が異なる店舗はありますか？あれば番号を選んでください（終了は空Enter）")
    for i, store in enumerate(stores, start=1):
        print(f"{i}: {store['store_name']}")
    while True:
        choice = input("番号（空Enterで終了）: ").strip()
        if not choice:
            break
        store = stores[int(choice) - 1]
        filename = input(f"{store['store_name']}の画像ファイル名: ").strip()
        overrides[store["store_id"]] = filename
    return overrides


def main():
    """対話形式でSHUFOO掲載用CSVと画像ZIPを生成する。"""
    base_dir = Path(__file__).parent
    config = load_config(base_dir / "config.json")
    pattern_key, pattern = prompt_pattern(config)
    if not pattern["stores"]:
        print(f"エラー: パターン「{pattern['label']}」に店舗が登録されていません。")
        return

    current_year = date.today().year
    start_date = prompt_date("掲載開始日", current_year)
    end_date = prompt_date("掲載終了日", current_year)
    start_dt, end_dt = compute_period(start_date, end_date)

    title = input("チラシタイトル: ").strip()
    default_image = input("既定の画像ファイル名: ").strip()
    overrides = prompt_overrides(pattern["stores"])

    rows = build_csv_rows(
        pattern["stores"], start_dt, end_dt, title, default_image, overrides
    )
    used_images = collect_used_images(rows)
    existing, missing = check_images_exist(used_images, base_dir)
    if missing:
        print(f"警告: 以下の画像ファイルが見つかりません: {', '.join(missing)}")
        if input("続行しますか？(y/N): ").strip().lower() != "y":
            print("処理を中止しました。")
            return

    csv_path = base_dir / pattern["csv_filename"]
    write_csv(rows, csv_path)

    zip_path = base_dir / pattern["zip_filename"]
    write_zip(existing, base_dir, zip_path)

    print(f"CSVを保存しました: {csv_path}（{len(rows)}件、例外{len(overrides)}件）")
    print(f"画像ZIPを保存しました: {zip_path}（{len(existing)}件）")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 既存の全ユニットテストが引き続き通ることを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: PASS（全14件、`main`関連の追加テストなし）

- [ ] **Step 3: 手動で対話フローを実行して動作確認する**

Run: `cd "日次業務/shufoo" && python make_shufoo_csv.py`

以下を入力して一連の流れを確認する:
1. パターン: `1`（お買い得チラシ）
2. 掲載開始日: `7/10`
3. 掲載終了日: `7/11`
4. チラシタイトル: `お買い得チラシ7月2週目テスト`
5. 既定の画像ファイル名: `7.10-11.JPG`
6. 例外店舗: 空Enter（なし）

Expected:
- `tirasi.csv`が上書きされ、cp932で開くと16店舗分の行があり、掲載開始日時が`2026/7/9 19:00`、終了日時が`2026/7/11 15:00`になっている
- `tirasi_images.zip`が生成され、`7.10-11.JPG`が1件だけ含まれている
- 完了メッセージに件数（16件、例外0件）が表示される

- [ ] **Step 4: 生成されたファイルを確認後、元のファイルに戻す（テスト実行による上書きを元に戻す）**

Run: `cd "日次業務/shufoo" && git status`

`tirasi.csv`が変更されている場合は、実データと相違ないか（店舗数・店舗名）を確認した上で、
そのままコミット対象に含めるか、`git checkout -- tirasi.csv`で元に戻すかを判断する。
（このステップは自動化ではなく、動作確認後の後片付けとして手動で行う）

- [ ] **Step 5: コミット**

```bash
git add "日次業務/shufoo/make_shufoo_csv.py"
git commit -m "feat(shufoo): 対話形式のCLI（パターン選択・入力・CSV/ZIP生成）を追加"
```

---

## 実行後の確認事項（人間が行うこと）

- 生成された`tirasi.csv`・`tirasiyasui.csv`・各ZIPを、実際にSHUFOOの管理画面にアップロードして
  受け付けられることを確認する（本自動化はローカルでのファイル生成のみを対象とし、
  SHUFOOへのアップロード自体は対象外）
- 店舗の追加・削除・パターン間の入れ替えが発生した場合は、`config.json`を直接編集する
