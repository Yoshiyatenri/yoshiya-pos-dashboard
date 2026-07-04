# メール件名キーワード検知＋AI緊急度判定 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `メール処理/` フォルダに、IMAPで新着メールを定期チェックし、件名キーワードに該当したメールをClaude APIで緊急度判定してCSVログに記録するスクリプト一式を作る。

**Architecture:** `mail_check.py`（IMAP接続・UID管理・CSV出力・オーケストレーション）と `ai_judge.py`（Claude APIによる緊急度判定、`SNS/planner.py` と同じ依存性注入パターン）に分割する。標準ライブラリ（`imaplib`, `email`, `json`, `csv`, `logging`）＋ `anthropic` ライブラリのみ使用。

**Tech Stack:** Python 3.12, `imaplib`（標準ライブラリ）, `anthropic`, `pytest`

参照仕様書: `docs/superpowers/specs/2026-07-04-mail-keyword-check-design.md`

## Global Constraints

- コメント・ログメッセージは日本語で書く
- 設定値（IMAPホスト・ポート・認証情報・APIキー）は `config.json` に集約し、コードにハードコードしない
- IMAP接続先: `okashinodepart.net`、ポート143、SSLなし
- Claude APIモデルは `claude-sonnet-5`（`SNS/planner.py` と同じ）
- デバッグ用スクリプトは `check_*.py` / `debug_*.py` 命名で本番コードと分ける
- シンプルで読みやすいコードを優先し、過剰な抽象化はしない
- テストは `pytest`、外部依存（IMAP接続・Claude API）は `unittest.mock.MagicMock` で差し替える（`SNS/test_planner.py` と同じパターン）

---

## File Structure

| ファイル | 責務 |
|---|---|
| `メール処理/config.json` | 設定値の雛形（実値はユーザーが入力） |
| `メール処理/.gitignore` | `config.json` 等をGit管理外にする |
| `メール処理/requirements.txt` | `anthropic`, `pytest` |
| `メール処理/mail_check.py` | メイン処理（IMAP・UID管理・CSV出力・オーケストレーション） |
| `メール処理/ai_judge.py` | Claude APIによる緊急度・返信要否判定 |
| `メール処理/test_mail_check.py` | `mail_check.py` のテスト |
| `メール処理/test_ai_judge.py` | `ai_judge.py` のテスト |
| `メール処理/check_mail_imap.py` | デバッグ用：IMAP接続確認・件名一覧表示 |
| `メール処理/run_mail_check.bat` | タスクスケジューラから呼ぶ起動用バッチ |
| `メール処理/setup_scheduler.bat` | タスクスケジューラへの登録用バッチ |

`メール処理/processed_uids.json` と `メール処理/mail_check_log.csv` は実行時に自動生成される（コミット対象外）。

---

### Task 1: プロジェクト雛形

**Files:**
- Create: `メール処理/.gitignore`
- Create: `メール処理/requirements.txt`
- Create: `メール処理/config.json`

**Interfaces:**
- Produces: `config.json` のキー構造（`imap_host`, `imap_port`, `use_ssl`, `user`, `password`, `keywords`, `anthropic_api_key`）— 以降の全タスクがこの構造に依存する

- [ ] **Step 1: `.gitignore` を作成する**

`メール処理/.gitignore`:
```
config.json
processed_uids.json
mail_check_log.csv
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 2: `requirements.txt` を作成する**

`メール処理/requirements.txt`:
```
anthropic
pytest
```

- [ ] **Step 3: `config.json` の雛形を作成する**

`メール処理/config.json`:
```json
{
  "imap_host": "okashinodepart.net",
  "imap_port": 143,
  "use_ssl": false,
  "user": "tenri@okashinodepart.net",
  "password": "ここにメールパスワードを入力してください",
  "keywords": ["オンライン集計", "締め切り", "至急"],
  "anthropic_api_key": "ここにClaude APIキーを入力してください"
}
```

- [ ] **Step 4: 依存パッケージをインストールする**

Run: `pip install -r "メール処理/requirements.txt"`
Expected: `anthropic` と `pytest` がインストールされる

- [ ] **Step 5: Commit**

```bash
git add メール処理/.gitignore メール処理/requirements.txt
git commit -m "feat(メール処理): プロジェクト雛形を追加"
```

Note: `config.json` は `.gitignore`対象のため `git add` しない。

---

### Task 2: config.json 読み込み

**Files:**
- Create: `メール処理/mail_check.py`
- Create: `メール処理/test_mail_check.py`

**Interfaces:**
- Consumes: Task 1の `config.json` 構造
- Produces: `load_config(path="config.json") -> dict` — 以降の全タスクがこの関数でconfigを取得する

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/test_mail_check.py`:
```python
import json
from mail_check import load_config


def test_load_config_reads_json_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"imap_host": "example.com", "keywords": ["至急"]}),
        encoding="utf-8",
    )

    result = load_config(str(config_path))

    assert result["imap_host"] == "example.com"
    assert result["keywords"] == ["至急"]
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py::test_load_config_reads_json_file -v`
Expected: FAIL（`mail_check` モジュールまたは `load_config` が存在しない）

- [ ] **Step 3: 最小限の実装をする**

`メール処理/mail_check.py`:
```python
"""IMAPで新着メールをチェックし、件名キーワードに該当したメールをAI判定してログに残す。"""
import json

CONFIG_PATH = "config.json"


def load_config(path=CONFIG_PATH):
    """config.jsonを読み込んで辞書として返す。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py::test_load_config_reads_json_file -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add メール処理/mail_check.py メール処理/test_mail_check.py
git commit -m "feat(メール処理): config.json読み込み機能を追加"
```

---

### Task 3: 処理済みUID管理

**Files:**
- Modify: `メール処理/mail_check.py`
- Modify: `メール処理/test_mail_check.py`

**Interfaces:**
- Produces:
  - `load_processed_uids(path="processed_uids.json") -> set[str] | None`（ファイルが無ければ `None` を返す＝初回実行の合図）
  - `save_processed_uids(uids: set[str], path="processed_uids.json") -> None`

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/test_mail_check.py` に追記:
```python
from mail_check import load_processed_uids, save_processed_uids


def test_load_processed_uids_returns_none_when_file_missing(tmp_path):
    path = tmp_path / "processed_uids.json"

    result = load_processed_uids(str(path))

    assert result is None


def test_save_and_load_processed_uids_roundtrip(tmp_path):
    path = tmp_path / "processed_uids.json"

    save_processed_uids({"1", "2", "3"}, str(path))
    result = load_processed_uids(str(path))

    assert result == {"1", "2", "3"}
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k processed_uids -v`
Expected: FAIL（`load_processed_uids` / `save_processed_uids` が存在しない）

- [ ] **Step 3: 実装する**

`メール処理/mail_check.py` に追記:
```python
import os

PROCESSED_UIDS_PATH = "processed_uids.json"


def load_processed_uids(path=PROCESSED_UIDS_PATH):
    """処理済みUIDの集合を読み込む。ファイルが無ければ初回実行としてNoneを返す。"""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return set(json.load(f))


def save_processed_uids(uids, path=PROCESSED_UIDS_PATH):
    """処理済みUIDの集合を保存する。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(uids), f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k processed_uids -v`
Expected: PASS（2件とも）

- [ ] **Step 5: Commit**

```bash
git add メール処理/mail_check.py メール処理/test_mail_check.py
git commit -m "feat(メール処理): 処理済みUID管理機能を追加"
```

---

### Task 4: 件名キーワード判定

**Files:**
- Modify: `メール処理/mail_check.py`
- Modify: `メール処理/test_mail_check.py`

**Interfaces:**
- Produces: `match_keywords(subject: str, keywords: list[str]) -> list[str]`（該当したキーワードのリスト。該当なしは空リスト）

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/test_mail_check.py` に追記:
```python
from mail_check import match_keywords


def test_match_keywords_returns_matched_list():
    result = match_keywords("【至急】オンライン集計のお願い", ["至急", "締め切り", "オンライン集計"])

    assert result == ["至急", "オンライン集計"]


def test_match_keywords_returns_empty_when_no_match():
    result = match_keywords("いつもお世話になっております", ["至急", "締め切り"])

    assert result == []
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k match_keywords -v`
Expected: FAIL（`match_keywords` が存在しない）

- [ ] **Step 3: 実装する**

`メール処理/mail_check.py` に追記:
```python
def match_keywords(subject, keywords):
    """件名に含まれるキーワードのリストを返す（部分一致）。"""
    return [kw for kw in keywords if kw in subject]
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k match_keywords -v`
Expected: PASS（2件とも）

- [ ] **Step 5: Commit**

```bash
git add メール処理/mail_check.py メール処理/test_mail_check.py
git commit -m "feat(メール処理): 件名キーワード判定機能を追加"
```

---

### Task 5: CSVログ追記

**Files:**
- Modify: `メール処理/mail_check.py`
- Modify: `メール処理/test_mail_check.py`

**Interfaces:**
- Produces:
  - `CSV_FIELDNAMES: list[str]`（列: `実行日時, メール日時, 差出人, 件名, ヒットキーワード, 緊急度, 返信要否, AI判断理由`）
  - `append_log(row: dict, path="mail_check_log.csv") -> None`

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/test_mail_check.py` に追記:
```python
import csv
from mail_check import append_log, CSV_FIELDNAMES


def test_append_log_writes_header_on_first_call(tmp_path):
    path = tmp_path / "mail_check_log.csv"
    row = {name: f"値-{name}" for name in CSV_FIELDNAMES}

    append_log(row, str(path))

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert reader.fieldnames == CSV_FIELDNAMES
    assert rows == [row]


def test_append_log_appends_without_duplicate_header(tmp_path):
    path = tmp_path / "mail_check_log.csv"
    row1 = {name: "1" for name in CSV_FIELDNAMES}
    row2 = {name: "2" for name in CSV_FIELDNAMES}

    append_log(row1, str(path))
    append_log(row2, str(path))

    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k append_log -v`
Expected: FAIL（`append_log` / `CSV_FIELDNAMES` が存在しない）

- [ ] **Step 3: 実装する**

`メール処理/mail_check.py` に追記:
```python
import csv

LOG_CSV_PATH = "mail_check_log.csv"

CSV_FIELDNAMES = [
    "実行日時",
    "メール日時",
    "差出人",
    "件名",
    "ヒットキーワード",
    "緊急度",
    "返信要否",
    "AI判断理由",
]


def append_log(row, path=LOG_CSV_PATH):
    """検知結果を1行CSVに追記する。ファイルが無ければヘッダーも書く。"""
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k append_log -v`
Expected: PASS（2件とも）

- [ ] **Step 5: Commit**

```bash
git add メール処理/mail_check.py メール処理/test_mail_check.py
git commit -m "feat(メール処理): CSVログ追記機能を追加"
```

---

### Task 6: IMAP接続・UID取得

**Files:**
- Modify: `メール処理/mail_check.py`
- Modify: `メール処理/test_mail_check.py`

**Interfaces:**
- Consumes: Task 2の `load_config()` が返す辞書（`imap_host`, `imap_port`, `user`, `password` キー）
- Produces:
  - `connect_imap(config: dict) -> imaplib.IMAP4`（ログイン済み・INBOX選択済みの接続を返す）
  - `fetch_all_uids(conn) -> list[bytes]`

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/test_mail_check.py` に追記:
```python
from unittest.mock import MagicMock
from mail_check import fetch_all_uids


def test_fetch_all_uids_returns_uid_list():
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("OK", [b"1 2 3"])

    result = fetch_all_uids(fake_conn)

    assert result == [b"1", b"2", b"3"]
    fake_conn.uid.assert_called_once_with("search", None, "ALL")


def test_fetch_all_uids_raises_on_error_status():
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("NO", [b""])

    try:
        fetch_all_uids(fake_conn)
        assert False, "例外が発生するはず"
    except RuntimeError:
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k fetch_all_uids -v`
Expected: FAIL（`fetch_all_uids` が存在しない）

- [ ] **Step 3: 実装する**

`メール処理/mail_check.py` に追記:
```python
import imaplib


def connect_imap(config):
    """IMAP4でログインし、INBOXを選択した接続を返す。"""
    conn = imaplib.IMAP4(config["imap_host"], config["imap_port"])
    conn.login(config["user"], config["password"])
    conn.select("INBOX")
    return conn


def fetch_all_uids(conn):
    """INBOX内の全メールUIDを取得する。"""
    status, data = conn.uid("search", None, "ALL")
    if status != "OK":
        raise RuntimeError(f"UID検索に失敗しました: status={status}")
    return data[0].split()
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k fetch_all_uids -v`
Expected: PASS（2件とも）

- [ ] **Step 5: Commit**

```bash
git add メール処理/mail_check.py メール処理/test_mail_check.py
git commit -m "feat(メール処理): IMAP接続・UID取得機能を追加"
```

---

### Task 7: メールヘッダー・本文取得

**Files:**
- Modify: `メール処理/mail_check.py`
- Modify: `メール処理/test_mail_check.py`

**Interfaces:**
- Consumes: Task 6の `conn`（IMAP接続）
- Produces:
  - `fetch_header(conn, uid: bytes) -> dict`（キー: `subject`, `from`, `date`）
  - `fetch_body(conn, uid: bytes) -> str`（プレーンテキスト本文。text/plainが無ければtext/htmlからタグを除去して返す）

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/test_mail_check.py` に追記:
```python
import base64
from mail_check import fetch_header, fetch_body


def test_fetch_header_parses_subject_from_date():
    encoded_subject = base64.b64encode("至急のご連絡".encode("utf-8")).decode("ascii")
    raw_header = (
        f"Subject: =?utf-8?B?{encoded_subject}?=\r\n"
        "From: Head Office <honbu@example.com>\r\n"
        "Date: Sat, 04 Jul 2026 09:00:00 +0900\r\n"
    ).encode("utf-8")
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("OK", [(b"1 (BODY[HEADER.FIELDS])", raw_header)])

    result = fetch_header(fake_conn, b"1")

    assert result["subject"] == "至急のご連絡"
    assert "honbu@example.com" in result["from"]
    assert result["date"] == "Sat, 04 Jul 2026 09:00:00 +0900"


def test_fetch_body_returns_plain_text():
    raw_message = (
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "本文のテキストです。"
    ).encode("utf-8")
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("OK", [(b"1 (BODY[])", raw_message)])

    result = fetch_body(fake_conn, b"1")

    assert result == "本文のテキストです。"


def test_fetch_body_strips_html_tags_when_only_html_available():
    raw_message = (
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        "<html><body><p>本文</p></body></html>"
    ).encode("utf-8")
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("OK", [(b"1 (BODY[])", raw_message)])

    result = fetch_body(fake_conn, b"1")

    assert "<" not in result
    assert "本文" in result
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k "fetch_header or fetch_body" -v`
Expected: FAIL（`fetch_header` / `fetch_body` が存在しない）

- [ ] **Step 3: 実装する**

`メール処理/mail_check.py` に追記:
```python
import email
import re
from email.header import decode_header


def _decode_mime_words(raw_value):
    """MIMEエンコードされたヘッダー文字列（件名・差出人）をデコードする。"""
    parts = decode_header(raw_value or "")
    result = []
    for text, charset in parts:
        if isinstance(text, bytes):
            result.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(text)
    return "".join(result)


def fetch_header(conn, uid):
    """メールの件名・差出人・日時を取得する。"""
    status, data = conn.uid(
        "fetch", uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])"
    )
    if status != "OK":
        raise RuntimeError(f"ヘッダー取得に失敗しました: uid={uid}")
    raw_header = data[0][1]
    msg = email.message_from_bytes(raw_header)
    return {
        "subject": _decode_mime_words(msg.get("Subject", "")),
        "from": _decode_mime_words(msg.get("From", "")),
        "date": msg.get("Date", ""),
    }


def _extract_text_from_message(msg):
    """メールから本文テキストを取り出す。text/plain優先、無ければtext/htmlのタグを除去する。"""
    plain_part = None
    html_part = None

    if msg.is_multipart():
        for part in msg.walk():
            disposition = part.get("Content-Disposition", "")
            if "attachment" in disposition:
                continue
            if part.get_content_type() == "text/plain" and plain_part is None:
                plain_part = part
            elif part.get_content_type() == "text/html" and html_part is None:
                html_part = part
        target = plain_part or html_part
    else:
        target = msg

    if target is None:
        return ""

    charset = target.get_content_charset() or "utf-8"
    payload = target.get_payload(decode=True) or b""
    text = payload.decode(charset, errors="replace")

    if target.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", "", text)

    return text


def fetch_body(conn, uid):
    """メール本文をプレーンテキストとして取得する。"""
    status, data = conn.uid("fetch", uid, "(BODY.PEEK[])")
    if status != "OK":
        raise RuntimeError(f"本文取得に失敗しました: uid={uid}")
    raw_message = data[0][1]
    msg = email.message_from_bytes(raw_message)
    return _extract_text_from_message(msg)
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k "fetch_header or fetch_body" -v`
Expected: PASS（3件とも）

- [ ] **Step 5: Commit**

```bash
git add メール処理/mail_check.py メール処理/test_mail_check.py
git commit -m "feat(メール処理): メールヘッダー・本文取得機能を追加"
```

---

### Task 8: AI緊急度判定

**Files:**
- Create: `メール処理/ai_judge.py`
- Create: `メール処理/test_ai_judge.py`

**Interfaces:**
- Produces:
  - `build_prompt(subject: str, body: str) -> str`
  - `judge_urgency(subject: str, body: str, api_key: str, client=None) -> dict`（キー: `urgency`, `reply_needed`, `reason`。失敗時は3キーとも `"AI判定失敗"` / エラー内容を設定）

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/test_ai_judge.py`:
```python
from unittest.mock import MagicMock
from ai_judge import build_prompt, judge_urgency


def test_build_prompt_includes_subject_and_body():
    prompt = build_prompt("至急のご連絡", "本文のテキストです。")

    assert "至急のご連絡" in prompt
    assert "本文のテキストです。" in prompt


def test_judge_urgency_parses_response():
    fake_response = MagicMock()
    fake_response.content = [
        MagicMock(text="緊急度: 高\n返信要否: 要\n理由: 締め切りが本日のため")
    ]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    result = judge_urgency("至急のご連絡", "本文", api_key="dummy", client=fake_client)

    assert result == {
        "urgency": "高",
        "reply_needed": "要",
        "reason": "締め切りが本日のため",
    }


def test_judge_urgency_returns_failure_dict_on_error():
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("APIエラー")

    result = judge_urgency("至急のご連絡", "本文", api_key="dummy", client=fake_client)

    assert result["urgency"] == "AI判定失敗"
    assert result["reply_needed"] == "AI判定失敗"
    assert "APIエラー" in result["reason"]
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && pytest test_ai_judge.py -v`
Expected: FAIL（`ai_judge` モジュールが存在しない）

- [ ] **Step 3: 実装する**

`メール処理/ai_judge.py`:
```python
"""Claude APIを使ってメールの緊急度・返信要否を判定する。"""
import re
import anthropic

CLAUDE_MODEL = "claude-sonnet-5"


def build_prompt(subject, body):
    """メール件名・本文からClaude APIに渡すプロンプト文を作る。"""
    return (
        "あなたは駄菓子店の店長を補佐するアシスタントです。\n"
        "以下のメールについて、緊急度と返信要否を判定してください。\n\n"
        f"件名: {subject}\n"
        f"本文:\n{body}\n\n"
        "次の形式で日本語で回答してください（他の文章は書かないでください）。\n"
        "緊急度: 高・中・低のいずれか1つ\n"
        "返信要否: 要・不要のいずれか1つ\n"
        "理由: 1文で簡潔に"
    )


def _extract_field(text, label):
    match = re.search(rf"{label}[:：]\s*(.+)", text)
    return match.group(1).strip() if match else None


def _parse_judgement(text):
    return {
        "urgency": _extract_field(text, "緊急度") or "不明",
        "reply_needed": _extract_field(text, "返信要否") or "不明",
        "reason": _extract_field(text, "理由") or "",
    }


def judge_urgency(subject, body, api_key, client=None):
    """メールの緊急度・返信要否をClaude APIで判定する。失敗時はAI判定失敗を返す。"""
    if client is None:
        client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt(subject, body)
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        return _parse_judgement(text)
    except Exception as error:
        print(f"AI判定に失敗しました: {error}")
        return {
            "urgency": "AI判定失敗",
            "reply_needed": "AI判定失敗",
            "reason": str(error),
        }
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && pytest test_ai_judge.py -v`
Expected: PASS（3件とも）

- [ ] **Step 5: Commit**

```bash
git add メール処理/ai_judge.py メール処理/test_ai_judge.py
git commit -m "feat(メール処理): AI緊急度判定機能を追加"
```

---

### Task 9: main()オーケストレーション

**Files:**
- Modify: `メール処理/mail_check.py`
- Modify: `メール処理/test_mail_check.py`

**Interfaces:**
- Consumes: Task 2〜8の全関数（`load_config`, `connect_imap`, `fetch_all_uids`, `load_processed_uids`, `save_processed_uids`, `match_keywords`, `fetch_header`, `fetch_body`, `append_log`, `ai_judge.judge_urgency`）
- Produces: `main() -> None`（スクリプトのエントリポイント）

- [ ] **Step 1: 失敗するテストを書く**

初回実行（ベースライン登録）と、2回目以降（新着検知）の2パターンをテストする。IMAP接続・Claude API・ファイルI/Oをすべてモックし、`main()` の分岐ロジックを検証する。

`メール処理/test_mail_check.py` に追記:
```python
from unittest.mock import patch, MagicMock
import mail_check


def test_main_baseline_registers_existing_uids_without_logging(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    fake_conn = MagicMock()

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1", b"2"]):
        mail_check.main()

    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1", "2"}
    assert not (tmp_path / "mail_check_log.csv").exists()


def test_main_logs_only_matched_new_mail(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids({"1"}, str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {
        b"1": {"subject": "既読メール", "from": "a@example.com", "date": "d1"},
        b"2": {"subject": "至急対応願います", "from": "b@example.com", "date": "d2"},
        b"3": {"subject": "普通の連絡", "from": "c@example.com", "date": "d3"},
    }

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1", b"2", b"3"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="本文"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "高", "reply_needed": "要", "reason": "理由"
         }) as fake_judge:
        mail_check.main()

    import csv
    with open(tmp_path / "mail_check_log.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["件名"] == "至急対応願います"
    assert rows[0]["ヒットキーワード"] == "至急"
    fake_judge.assert_called_once()

    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1", "2", "3"}
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -k main -v`
Expected: FAIL（`main` が存在しない、または `judge_urgency` がインポートされていない）

- [ ] **Step 3: 実装する**

`メール処理/mail_check.py` の先頭付近に追記:
```python
import logging
from datetime import datetime

from ai_judge import judge_urgency

LOG_FILE_PATH = "mail_check.log"
```

`メール処理/mail_check.py` の末尾に追記:
```python
def _setup_logger():
    logger = logging.getLogger("mail_check")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def main():
    """メールチェックのエントリポイント。"""
    logger = _setup_logger()
    config = load_config()

    try:
        conn = connect_imap(config)
    except Exception as error:
        logger.error(f"IMAP接続に失敗しました: {error}")
        return

    try:
        all_uids = {uid.decode() for uid in fetch_all_uids(conn)}
        processed = load_processed_uids()

        if processed is None:
            save_processed_uids(all_uids)
            logger.info(f"初回実行: 既存メール{len(all_uids)}件をベースライン登録しました")
            return

        new_uids = sorted(all_uids - processed, key=int)
        matched_count = 0

        for uid_str in new_uids:
            uid = uid_str.encode()
            header = fetch_header(conn, uid)
            matched = match_keywords(header["subject"], config["keywords"])

            if matched:
                body = fetch_body(conn, uid)
                judgement = judge_urgency(
                    header["subject"], body, config["anthropic_api_key"]
                )
                append_log({
                    "実行日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "メール日時": header["date"],
                    "差出人": header["from"],
                    "件名": header["subject"],
                    "ヒットキーワード": "・".join(matched),
                    "緊急度": judgement["urgency"],
                    "返信要否": judgement["reply_needed"],
                    "AI判断理由": judgement["reason"],
                })
                matched_count += 1

            processed.add(uid_str)

        save_processed_uids(processed)
        logger.info(
            f"実行完了: 新着{len(new_uids)}件中{matched_count}件がキーワードに該当しました"
        )
    finally:
        conn.logout()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -v`
Expected: PASS（これまでの全テストを含めてすべて成功）

- [ ] **Step 5: Commit**

```bash
git add メール処理/mail_check.py メール処理/test_mail_check.py
git commit -m "feat(メール処理): main()オーケストレーション処理を追加"
```

---

### Task 10: デバッグ用スクリプト

**Files:**
- Create: `メール処理/check_mail_imap.py`

**Interfaces:**
- Consumes: Task 2, 6, 7 の `load_config`, `connect_imap`, `fetch_all_uids`, `fetch_header`

- [ ] **Step 1: デバッグ用スクリプトを作成する**

`メール処理/check_mail_imap.py`:
```python
"""IMAP接続確認・件名一覧表示用のデバッグスクリプト（本番では使わない）。"""
from mail_check import load_config, connect_imap, fetch_all_uids, fetch_header


def main():
    config = load_config()
    print(f"接続先: {config['imap_host']}:{config['imap_port']}")

    conn = connect_imap(config)
    print("ログイン成功。INBOXを選択しました。")

    try:
        uids = fetch_all_uids(conn)
        print(f"メール件数: {len(uids)}")

        for uid in uids[-10:]:
            header = fetch_header(conn, uid)
            print(f"UID={uid.decode()} 件名={header['subject']} 差出人={header['from']}")
    finally:
        conn.logout()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 実際に接続して動作確認する**

Run: `cd "メール処理" && python check_mail_imap.py`
Expected: `config.json` に実際の認証情報を入力した状態で、ログイン成功メッセージと直近10件の件名一覧が表示される

- [ ] **Step 3: Commit**

```bash
git add メール処理/check_mail_imap.py
git commit -m "feat(メール処理): IMAP接続確認用デバッグスクリプトを追加"
```

---

### Task 11: タスクスケジューラ登録

**Files:**
- Create: `メール処理/run_mail_check.bat`
- Create: `メール処理/setup_scheduler.bat`

**Interfaces:**
- Consumes: Task 9 の `mail_check.py`

- [ ] **Step 1: 起動用バッチを作成する**

`メール処理/run_mail_check.bat`:
```bat
@echo off
cd /d "%~dp0"
python mail_check.py
```

- [ ] **Step 2: タスクスケジューラ登録用バッチを作成する**

2時間ごと（9,11,13,15,17,19時）に実行されるよう、開始9:00・繰り返し間隔120分・継続時間10時間で登録する。

`メール処理/setup_scheduler.bat`:
```bat
@echo off
:: Windowsタスクスケジューラに2時間ごと（9-19時）の自動実行を登録する
:: 管理者として実行してください

set TASK_NAME=よしや_メールチェック
set BAT_PATH=C:\one_tenri\OneDrive\HTY\vscode\メール処理\run_mail_check.bat

schtasks /create /tn "%TASK_NAME%" /tr "%BAT_PATH%" /sc DAILY /st 09:00 /ri 120 /du 10:00 /f /rl HIGHEST

if %errorlevel% equ 0 (
    echo タスクスケジューラへの登録が完了しました。
    echo 毎日9時から19時まで2時間ごとにメールチェックが実行されます。
) else (
    echo 登録に失敗しました。管理者として実行してください。
)
pause
```

- [ ] **Step 3: 手動でバッチを実行して動作確認する**

Run: `メール処理/run_mail_check.bat` をダブルクリックまたはコマンドラインから実行
Expected: `mail_check.log` にエラーが出力されず、`processed_uids.json` が生成/更新される

- [ ] **Step 4: Commit**

```bash
git add メール処理/run_mail_check.bat メール処理/setup_scheduler.bat
git commit -m "feat(メール処理): タスクスケジューラ登録用バッチを追加"
```

- [ ] **Step 5: タスクスケジューラに登録する（ユーザー操作）**

`メール処理/setup_scheduler.bat` を管理者として実行し、Windowsタスクスケジューラに登録する。

---

## Self-Review Notes

- **仕様カバレッジ:** 設計書の「処理の流れ」1〜6を Task 6・7・9 で、「AI緊急度判定」を Task 8 で、「実行タイミング」を Task 11 で、「エラー処理」を Task 9（IMAP接続失敗のログ記録・`processed_uids.json`未更新）と Task 8（AI判定失敗時の返り値）でカバー。「テスト方針」の初回ベースライン確認・新着該当メールのログ確認は Task 9 のテストで直接検証している。
- **プレースホルダー確認:** 各ステップに実コードを記載済み。TODO/TBD等は無し。
- **型・シグネチャの一貫性:** `judge_urgency(subject, body, api_key, client=None)` の呼び出し（Task 9 `main()`内）は Task 8 の定義と一致。`fetch_header`/`fetch_body` の `uid` はTask 6の `fetch_all_uids` が返す `bytes` 型に統一し、`processed_uids` 側は `str` の集合として扱う（`main()`内で `.decode()`/`.encode()` により変換）。
