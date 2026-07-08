# 通知メールの検索条件に日付条件を追加 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** メール件名キーワード検知ツールに、件名・本文に受信日または翌日の日付が含まれる場合も通知対象とする日付条件を追加する。

**Architecture:** `mail_check.py`に新規`match_dates`関数を追加し、`fetch_header`がIMAPのINTERNALDATE（受信日時）も取得するように拡張する。`main()`では新着メール全件の本文を取得し、件名+本文の結合テキストに対してキーワード判定と日付判定をOR条件で評価する。

**Tech Stack:** Python 3.12, `imaplib`, `email`, `datetime`, `re`, pytest, `unittest.mock`

## Global Constraints

- 日付条件の基準は「IMAPサーバー上の受信日時（INTERNALDATE）」を使う（メールのDateヘッダーは使わない）
- 対象日は「受信日当日」と「受信日の翌日」の2つ
- 日付の表記形式は「X月Y日」（例: `7月10日`）と「X/Y」（例: `7/10`）の両方を検出する。ゼロ埋めなし
- 「X/Y」形式は数字の部分一致による誤検出を防ぐため、前後が数字で続かないことを確認して検索する
- 判定条件はキーワード一致 **または** 日付一致のOR条件とする
- キーワード検索・日付検索とも、対象は「件名＋本文」の結合テキスト（現状の「件名のみ」から変更）
- 通知メールの「ヒットキーワード」欄は、キーワード一致時はキーワード文字列、日付一致のみの場合は`日付(7/10)`のように検出した日付文字列を表示する
- 既存の「メール1件の処理失敗が全体を止めない」仕組み（try/except/finally）は維持する

---

### Task 1: match_dates関数を追加

**Files:**
- Modify: `メール処理/mail_check.py`（関数追加、importの追加）
- Test: `メール処理/test_mail_check.py`（テスト追加、importの追加）

**Interfaces:**
- Consumes: なし（新規独立関数）
- Produces: `match_dates(text: str, received_date: datetime.date) -> list[str]` — `text`に受信日または翌日の日付が「X月Y日」形式または「X/Y」形式で含まれていれば、検出した日付を`"X/Y"`形式の文字列のリストで返す（両方の対象日が一致すれば2件になりうる）。一致がなければ空リスト`[]`を返す。後続タスクの`main()`から呼び出される。

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/test_mail_check.py`の先頭のimport文に`from datetime import date`を追加し、`from mail_check import match_keywords`の行に`match_dates`を追加する:

```python
from datetime import date
from mail_check import load_config, load_processed_uids, save_processed_uids, match_keywords, match_dates, fetch_all_uids, fetch_header, fetch_body
```

同じファイルの`test_match_keywords_returns_empty_when_no_match`の直後（50行目付近）に以下のテストを追加する:

```python
def test_match_dates_detects_received_date_kanji_format():
    result = match_dates("7月10日必着でお願いします", date(2026, 7, 10))

    assert result == ["7/10"]


def test_match_dates_detects_received_date_slash_format():
    result = match_dates("7/10までにご返信ください", date(2026, 7, 10))

    assert result == ["7/10"]


def test_match_dates_detects_next_day():
    result = match_dates("明日7/11までにお願いします", date(2026, 7, 10))

    assert result == ["7/11"]


def test_match_dates_handles_month_rollover():
    result = match_dates("8/1締め切りです", date(2026, 7, 31))

    assert result == ["8/1"]


def test_match_dates_no_match_returns_empty_list():
    result = match_dates("キーワードもない普通のメールです", date(2026, 7, 10))

    assert result == []


def test_match_dates_avoids_partial_match_false_positive():
    result = match_dates("7/10のイベントについて", date(2026, 7, 1))

    assert result == []
```

（最後のテストは、受信日が7/1・翌日が7/2のとき、本文中の「7/10」に部分一致して誤検出しないことを確認するもの）

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && python -m pytest test_mail_check.py -k match_dates -v`
Expected: FAIL（`ImportError: cannot import name 'match_dates'`）

- [ ] **Step 3: 最小限の実装を書く**

`メール処理/mail_check.py`の先頭のimport群（8行目`from email.header import decode_header`の直後）に以下を追加する:

```python
from datetime import timedelta
```

`match_keywords`関数（38-40行目）の直後に以下の関数を追加する:

```python
def match_dates(text, received_date):
    """件名+本文テキストに、受信日または翌日の日付が含まれていれば検出日付のリストを返す。"""
    hits = []
    for target_date in (received_date, received_date + timedelta(days=1)):
        month, day = target_date.month, target_date.day
        kanji_pattern = f"{month}月{day}日"
        slash_pattern = rf"(?<!\d){month}/{day}(?!\d)"
        if kanji_pattern in text or re.search(slash_pattern, text):
            hits.append(f"{month}/{day}")
    return hits
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && python -m pytest test_mail_check.py -k match_dates -v`
Expected: PASS（6 passed）

- [ ] **Step 5: コミット**

```bash
git add "メール処理/mail_check.py" "メール処理/test_mail_check.py"
git commit -m "feat(メール処理): 受信日・翌日の日付を検出するmatch_dates関数を追加"
```

---

### Task 2: fetch_headerで受信日(INTERNALDATE)を取得する

**Files:**
- Modify: `メール処理/mail_check.py:71-84`（`fetch_header`関数）
- Test: `メール処理/test_mail_check.py:70-84`（既存テストの置き換え）

**Interfaces:**
- Consumes: `imaplib.Internaldate2tuple`（標準ライブラリ）
- Produces: `fetch_header(conn, uid)`の返り値の辞書に`"received_date"`キー（`datetime.date`型）を追加する。既存の`"subject"`, `"from"`, `"date"`キーは変更しない。後続タスクの`main()`が`header["received_date"]`を`match_dates`に渡す。

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/test_mail_check.py`の`test_fetch_header_parses_subject_from_date`（70-84行目）を、以下の内容で置き換える:

```python
def test_fetch_header_parses_subject_from_date_and_received_date():
    encoded_subject = base64.b64encode("至急のご連絡".encode("utf-8")).decode("ascii")
    raw_header = (
        f"Subject: =?utf-8?B?{encoded_subject}?=\r\n"
        "From: Head Office <honbu@example.com>\r\n"
        "Date: Sat, 04 Jul 2026 09:00:00 +0900\r\n"
    ).encode("utf-8")
    raw_meta = b'1 (INTERNALDATE "04-Jul-2026 09:00:00 +0900" BODY[HEADER.FIELDS (SUBJECT FROM DATE)] {123}'
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("OK", [(raw_meta, raw_header)])

    result = fetch_header(fake_conn, b"1")

    assert result["subject"] == "至急のご連絡"
    assert "honbu@example.com" in result["from"]
    assert result["date"] == "Sat, 04 Jul 2026 09:00:00 +0900"
    assert result["received_date"] == date(2026, 7, 4)
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && python -m pytest test_mail_check.py -k test_fetch_header_parses_subject_from_date_and_received_date -v`
Expected: FAIL（`KeyError: 'received_date'`）

- [ ] **Step 3: 最小限の実装を書く**

`メール処理/mail_check.py`の先頭のimport群に`from datetime import date, timedelta`（Task 1で追加した`timedelta`と合わせて1行にまとめる）を書く:

```python
from datetime import date, timedelta
```

`fetch_header`関数（71-84行目）を以下の内容で置き換える:

```python
def fetch_header(conn, uid):
    """メールの件名・差出人・日時・受信日を取得する。"""
    status, data = conn.uid(
        "fetch", uid, "(INTERNALDATE BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])"
    )
    if status != "OK":
        raise RuntimeError(f"ヘッダー取得に失敗しました: uid={uid}")
    raw_response = data[0]
    internal_date_tuple = imaplib.Internaldate2tuple(raw_response[0])
    raw_header = raw_response[1]
    msg = email.message_from_bytes(raw_header)
    return {
        "subject": _decode_mime_words(msg.get("Subject", "")),
        "from": _decode_mime_words(msg.get("From", "")),
        "date": msg.get("Date", ""),
        "received_date": date(*internal_date_tuple[:3]),
    }
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && python -m pytest test_mail_check.py -v`
Expected: PASS（既存テストも含めて全件成功。`test_fetch_header_parses_subject_from_date`という名前のテストはもう存在しない）

- [ ] **Step 5: コミット**

```bash
git add "メール処理/mail_check.py" "メール処理/test_mail_check.py"
git commit -m "feat(メール処理): fetch_headerでIMAPのINTERNALDATEから受信日を取得"
```

---

### Task 3: main()を新ロジックに統合する

**Files:**
- Modify: `メール処理/mail_check.py:38-40`（`match_keywords`のdocstring）, `メール処理/mail_check.py:138-201`（`main`関数）
- Test: `メール処理/test_mail_check.py`（既存の`main`系テストを修正、新規テストを追加）

**Interfaces:**
- Consumes: `match_keywords(text, keywords)`（既存, Task 1以前から存在）, `match_dates(text, received_date)`（Task 1で追加）, `fetch_header(conn, uid)`が返す`"received_date"`キー（Task 2で追加）
- Produces: `main()`の`matches`リストの各辞書は、`"ヒットキーワード"`の値がキーワード一致時はキーワード文字列（`"・"`区切り）、日付一致のみの場合は`"日付(X/Y)"`形式（複数該当時は`"・"`区切り）になる。この形式は変更しない（`notifier.py`はこの辞書をそのまま使うため、`notifier.py`への変更は不要）。

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/mail_check.py`の`match_keywords`関数（38-40行目）のdocstringを以下に変更する（動作は変更しない）:

```python
def match_keywords(text, keywords):
    """件名+本文の結合テキストに含まれるキーワードのリストを返す（部分一致）。"""
    return [kw for kw in keywords if kw in text]
```

`メール処理/test_mail_check.py`の既存の`main`系テストのヘッダー辞書に`"received_date"`キーを追加し、本文取得が全件で行われることに対応させる。以下の4つのテスト関数を、それぞれ以下の内容に置き換える。

`test_main_sends_notification_for_matched_new_mail`（139-172行目）を置き換え:

```python
def test_main_sends_notification_for_matched_new_mail(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids({"1"}, str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {
        b"1": {"subject": "既読メール", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 4)},
        b"2": {"subject": "至急対応願います", "from": "b@example.com", "date": "d2", "received_date": date(2026, 7, 4)},
        b"3": {"subject": "普通の連絡", "from": "c@example.com", "date": "d3", "received_date": date(2026, 7, 4)},
    }

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1", b"2", b"3"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="本文"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "高", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_called_once()
    matches_arg = fake_send.call_args[0][0]
    assert len(matches_arg) == 1
    assert matches_arg[0]["件名"] == "至急対応願います"
    assert matches_arg[0]["ヒットキーワード"] == "至急"
    assert matches_arg[0]["緊急度"] == "高"

    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1", "2", "3"}
```

`test_main_skips_notification_when_no_matches`（175-194行目）を置き換え:

```python
def test_main_skips_notification_when_no_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {b"1": {"subject": "普通の連絡", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 4)}}

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="本文"), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_not_called()
    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1"}
```

`test_main_continues_after_one_uid_fetch_fails`（197-232行目）を置き換え:

```python
def test_main_continues_after_one_uid_fetch_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {
        b"1": {"subject": "至急対応願います", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 4)},
        b"3": {"subject": "普通の連絡", "from": "c@example.com", "date": "d3", "received_date": date(2026, 7, 4)},
    }

    def fake_fetch_header(conn, uid):
        if uid == b"2":
            raise RuntimeError("壊れたメッセージ")
        return headers[uid]

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1", b"2", b"3"]), \
         patch.object(mail_check, "fetch_header", side_effect=fake_fetch_header), \
         patch.object(mail_check, "fetch_body", return_value="本文"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "高", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_called_once()
    matches_arg = fake_send.call_args[0][0]
    assert len(matches_arg) == 1
    assert matches_arg[0]["件名"] == "至急対応願います"

    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1", "2", "3"}
```

`test_main_logs_details_when_notification_send_fails`（235-259行目）を置き換え:

```python
def test_main_logs_details_when_notification_send_fails(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {b"1": {"subject": "至急対応願います", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 4)}}

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="本文"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "高", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email", side_effect=RuntimeError("送信エラー")), \
         caplog.at_level("ERROR", logger="mail_check"):
        mail_check.main()

    assert any("送信に失敗しました" in message for message in caplog.messages)
    assert any("至急対応願います" in message for message in caplog.messages)
```

さらに、ファイル末尾に以下の新規テストを追加する（キーワードには一致しないが日付にのみ一致するケース）:

```python
def test_main_sends_notification_for_date_matched_mail_without_keyword(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {
        b"1": {"subject": "明日の件について", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 10)},
    }

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="7/11までにご確認をお願いします"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "中", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_called_once()
    matches_arg = fake_send.call_args[0][0]
    assert len(matches_arg) == 1
    assert matches_arg[0]["ヒットキーワード"] == "日付(7/11)"
```

続けて、以下の新規テストも追加する（件名には一致しないが本文にキーワードが含まれるケース。「件名+本文」を検索範囲にしたことを確認するため）:

```python
def test_main_sends_notification_for_keyword_matched_in_body_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {
        b"1": {"subject": "いつもの連絡です", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 4)},
    }

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="本文中に至急の対応をお願いします"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "高", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_called_once()
    matches_arg = fake_send.call_args[0][0]
    assert len(matches_arg) == 1
    assert matches_arg[0]["ヒットキーワード"] == "至急"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && python -m pytest test_mail_check.py -v`
Expected: FAIL（`test_main_sends_notification_for_date_matched_mail_without_keyword`と`test_main_sends_notification_for_keyword_matched_in_body_only`が失敗する。他のmain系テストは、`main()`がまだ本文を全件取得していないため、日付判定に使う`received_date`が未使用のままでも現状の実装なら通ってしまう可能性があるが、Step 3実装後との差分確認のため一旦このまま実行する）

- [ ] **Step 3: 最小限の実装を書く**

`メール処理/mail_check.py`の`main`関数（138-201行目）のうち、`for uid_str in new_uids:`ループ内（161-183行目）を以下の内容で置き換える:

```python
        for uid_str in new_uids:
            try:
                uid = uid_str.encode()
                header = fetch_header(conn, uid)
                body = fetch_body(conn, uid)
                combined_text = header["subject"] + "\n" + body

                matched_keywords = match_keywords(combined_text, config["keywords"])
                matched_dates = match_dates(combined_text, header["received_date"])

                if matched_keywords or matched_dates:
                    judgement = judge_urgency(
                        header["subject"], body, config["anthropic_api_key"]
                    )
                    if matched_keywords:
                        hit_label = "・".join(matched_keywords)
                    else:
                        hit_label = "・".join(f"日付({d})" for d in matched_dates)
                    matches.append({
                        "差出人": header["from"],
                        "件名": header["subject"],
                        "ヒットキーワード": hit_label,
                        "緊急度": judgement["urgency"],
                        "返信要否": judgement["reply_needed"],
                        "AI判断理由": judgement["reason"],
                    })
            except Exception as error:
                logger.error(f"メール処理に失敗しました: uid={uid_str}: {error}")
            finally:
                processed.add(uid_str)
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && python -m pytest test_mail_check.py -v`
Expected: PASS（全件成功）

- [ ] **Step 5: コミット**

```bash
git add "メール処理/mail_check.py" "メール処理/test_mail_check.py"
git commit -m "feat(メール処理): キーワード・日付のOR条件で通知判定するようmain()を変更"
```

---

### Task 4: 使い方.mdを更新する

**Files:**
- Modify: `メール処理/使い方.md:9-16`（「このツールが行うこと」セクション）

**Interfaces:**
- Consumes: Task 1-3で確定した挙動（キーワード一致 or 日付一致のOR条件、件名+本文が検索対象）
- Produces: なし（ドキュメントのみ）

- [ ] **Step 1: 該当セクションを書き換える**

`メール処理/使い方.md`の「## 1. このツールが行うこと」セクション（9-16行目）を以下の内容で置き換える:

```markdown
## 1. このツールが行うこと

1. 指定したメールアドレス（社内メール）に届くメールを自動で確認する
2. 件名・本文のいずれかに、以下のどちらかが含まれていないかチェックする
   - 登録しておいたキーワード（「至急」「締め切り」など）
   - メールが届いた日、またはその翌日の日付（「7月10日」「7/10」のような表記）
3. 該当したメールについて、Claude AIに「緊急度」と「返信が必要か」を判定させる
4. 該当メールが1件でもあれば、それらを**まとめた通知メール1通**があなたのメールアドレスに届く
5. 該当メールが0件の場合は、何も送られません

**やること（あなたの作業）は「`config.json`で設定」と「実行予約（タスクスケジューラ）」だけです。**
```

- [ ] **Step 2: 変更内容を確認する**

`メール処理/使い方.md`を開き、「## 1. このツールが行うこと」セクションが書き換わっていることを目視確認する（ドキュメントのみの変更のためテストコマンドはなし）。

- [ ] **Step 3: コミット**

```bash
git add "メール処理/使い方.md"
git commit -m "docs(メール処理): 日付条件の追加を使い方マニュアルに反映"
```
