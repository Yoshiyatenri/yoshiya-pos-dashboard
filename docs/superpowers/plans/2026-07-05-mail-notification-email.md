# CSV出力→メール通知への切り替え 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `メール処理/`ツールの検知結果の記録先を、`mail_check_log.csv`への追記から、指定メールアドレスへの通知メール送信に切り替える。

**Architecture:** 新規`notifier.py`（本文組み立て・SMTP送信）を追加し、`mail_check.py`の`append_log`/CSV関連コードを削除して`main()`から`notifier.py`を呼び出す形に変更する。

**Tech Stack:** Python 3.12, `smtplib`（標準ライブラリ）, `pytest`, `unittest.mock`

参照仕様書: `docs/superpowers/specs/2026-07-05-mail-notification-email-design.md`

## Global Constraints

- コメント・ログメッセージは日本語で書く
- SMTP接続先: `okashinodepart.net`、ポート587、STARTTLS
- SMTP認証はIMAPと同じ`user`/`password`を流用する（`config.json`の既存キー）
- `config.json`に`smtp_host`, `smtp_port`, `notify_to`を追加する（実際の値の入力はユーザー自身が行うため、コードやテストでは実値をハードコードしない）
- 該当メールが1件もない場合は通知メールを送信しない
- 通知メール送信に失敗した場合は、`matches`の詳細（件名・緊急度等）を`mail_check.log`に記録する
- テストは`pytest`、外部依存（SMTP・IMAP・Claude API）は`unittest.mock`で差し替える
- シンプルで読みやすいコードを優先し、過剰な抽象化はしない

---

## File Structure

| ファイル | 責務 |
|---|---|
| `メール処理/notifier.py` | **新規**。通知メールの本文組み立て・SMTP送信 |
| `メール処理/test_notifier.py` | **新規**。`notifier.py`のテスト |
| `メール処理/mail_check.py` | `append_log`/`CSV_FIELDNAMES`/`LOG_CSV_PATH`を削除、`main()`から`notifier.py`を呼び出すよう変更 |
| `メール処理/test_mail_check.py` | CSV関連テストを削除、メール送信呼び出しを検証するテストに変更 |
| `メール処理/.gitignore` | `mail_check_log.csv`の行を削除 |
| `メール処理/使い方.md` | CSV確認の説明をメール通知の説明に更新 |

---

### Task 1: notifier.py の新規作成

**Files:**
- Create: `メール処理/notifier.py`
- Create: `メール処理/test_notifier.py`

**Interfaces:**
- Produces:
  - `build_email_body(matches: list[dict]) -> str`（`matches`の各要素は`差出人`, `件名`, `ヒットキーワード`, `緊急度`, `返信要否`, `AI判断理由`キーを持つ辞書）
  - `send_notification_email(matches: list[dict], config: dict) -> None`（`config`は`smtp_host`, `smtp_port`, `user`, `password`, `notify_to`キーを使用。送信失敗時は例外をそのまま呼び出し元に伝播させる）

- [ ] **Step 1: 失敗するテストを書く**

`メール処理/test_notifier.py`:
```python
from unittest.mock import MagicMock, patch
from notifier import build_email_body, send_notification_email


def test_build_email_body_includes_all_match_fields():
    matches = [
        {
            "差出人": "本部 <honbu@example.com>",
            "件名": "至急対応願います",
            "ヒットキーワード": "至急",
            "緊急度": "高",
            "返信要否": "要",
            "AI判断理由": "締め切りが本日のため",
        }
    ]

    body = build_email_body(matches)

    assert "1件" in body
    assert "本部 <honbu@example.com>" in body
    assert "至急対応願います" in body
    assert "ヒットキーワード: 至急" in body
    assert "緊急度: 高" in body
    assert "返信要否: 要" in body
    assert "締め切りが本日のため" in body


def test_build_email_body_includes_count_for_multiple_matches():
    matches = [
        {"差出人": "a@example.com", "件名": "件名1", "ヒットキーワード": "至急",
         "緊急度": "高", "返信要否": "要", "AI判断理由": "理由1"},
        {"差出人": "b@example.com", "件名": "件名2", "ヒットキーワード": "締め切り",
         "緊急度": "中", "返信要否": "不要", "AI判断理由": "理由2"},
    ]

    body = build_email_body(matches)

    assert "2件" in body
    assert "件名1" in body
    assert "件名2" in body


def test_send_notification_email_sends_via_smtp_with_starttls():
    matches = [
        {"差出人": "a@example.com", "件名": "至急対応願います", "ヒットキーワード": "至急",
         "緊急度": "高", "返信要否": "要", "AI判断理由": "理由"}
    ]
    config = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "user": "tenri@okashinodepart.net",
        "password": "secret",
        "notify_to": "hanakiti0811@gmail.com",
    }
    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value = fake_smtp

    with patch("notifier.smtplib.SMTP", return_value=fake_smtp) as fake_smtp_cls:
        send_notification_email(matches, config)

    fake_smtp_cls.assert_called_once_with("smtp.example.com", 587)
    fake_smtp.starttls.assert_called_once()
    fake_smtp.login.assert_called_once_with("tenri@okashinodepart.net", "secret")
    fake_smtp.send_message.assert_called_once()

    sent_message = fake_smtp.send_message.call_args[0][0]
    assert sent_message["From"] == "tenri@okashinodepart.net"
    assert sent_message["To"] == "hanakiti0811@gmail.com"
    assert "1件" in sent_message["Subject"]


def test_send_notification_email_raises_when_smtp_fails():
    matches = [
        {"差出人": "a@example.com", "件名": "件名", "ヒットキーワード": "至急",
         "緊急度": "高", "返信要否": "要", "AI判断理由": "理由"}
    ]
    config = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "user": "u",
        "password": "p",
        "notify_to": "to@example.com",
    }
    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value = fake_smtp
    fake_smtp.login.side_effect = RuntimeError("認証エラー")

    with patch("notifier.smtplib.SMTP", return_value=fake_smtp):
        try:
            send_notification_email(matches, config)
            assert False, "例外が発生するはず"
        except RuntimeError:
            pass
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && pytest test_notifier.py -v`
Expected: FAIL（`notifier`モジュールが存在しない）

- [ ] **Step 3: 実装する**

`メール処理/notifier.py`:
```python
"""検知結果をまとめて通知メールとして送信する。"""
import smtplib
from email.message import EmailMessage


def build_email_body(matches):
    """検知したメールのリストから、まとめて1通分の本文テキストを組み立てる。"""
    separator = "-" * 40
    lines = [f"以下のキーワード該当メールを検知しました（{len(matches)}件）。", ""]

    for match in matches:
        lines.append(separator)
        lines.append(f"差出人: {match['差出人']}")
        lines.append(f"件名: {match['件名']}")
        lines.append(f"ヒットキーワード: {match['ヒットキーワード']}")
        lines.append(f"緊急度: {match['緊急度']}")
        lines.append(f"返信要否: {match['返信要否']}")
        lines.append(f"理由: {match['AI判断理由']}")
    lines.append(separator)

    return "\n".join(lines)


def send_notification_email(matches, config):
    """検知結果をまとめて通知メールとして送信する。失敗時は例外を呼び出し元に伝播させる。"""
    message = EmailMessage()
    message["Subject"] = f"メールチェック結果: {len(matches)}件検知"
    message["From"] = config["user"]
    message["To"] = config["notify_to"]
    message.set_content(build_email_body(matches))

    with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as smtp:
        smtp.starttls()
        smtp.login(config["user"], config["password"])
        smtp.send_message(message)
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && pytest test_notifier.py -v`
Expected: PASS（4件とも）

- [ ] **Step 5: Commit**

```bash
git add メール処理/notifier.py メール処理/test_notifier.py
git commit -m "feat(メール処理): 通知メール送信機能を追加"
```

---

### Task 2: main()をメール通知に統合し、CSV関連コードを削除する

**Files:**
- Modify: `メール処理/mail_check.py`
- Modify: `メール処理/test_mail_check.py`

**Interfaces:**
- Consumes: Task 1の`send_notification_email(matches, config)`
- Produces: `main()`の新しい動作（`matches`リストを組み立て、非空なら`send_notification_email`を呼ぶ）

- [ ] **Step 1: test_mail_check.py を書き換える**

まず、ファイル冒頭のimportを次のように変更する（`csv`・`append_log`・`CSV_FIELDNAMES`を削除し、代わりに何もインポート追加はしない）。

`メール処理/test_mail_check.py`の1〜5行目を置き換え:
```python
import json
import base64
from unittest.mock import MagicMock
from mail_check import load_config, load_processed_uids, save_processed_uids, match_keywords, fetch_all_uids, fetch_header, fetch_body
```

次に、`test_append_log_writes_header_on_first_call`と`test_append_log_appends_without_duplicate_header`の2つのテスト関数を**削除**する（50〜76行目付近、`csv`・`CSV_FIELDNAMES`を使っている2つのテスト）。

最後に、ファイル末尾の3つの`test_main_*`テストを、以下の内容に**丸ごと置き換える**（`import csv`の重複行も削除される）。

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
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1", b"2"]), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1", "2"}
    fake_send.assert_not_called()


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


def test_main_skips_notification_when_no_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {b"1": {"subject": "普通の連絡", "from": "a@example.com", "date": "d1"}}

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_not_called()
    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1"}


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
        b"1": {"subject": "至急対応願います", "from": "a@example.com", "date": "d1"},
        b"3": {"subject": "普通の連絡", "from": "c@example.com", "date": "d3"},
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


def test_main_logs_details_when_notification_send_fails(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {b"1": {"subject": "至急対応願います", "from": "a@example.com", "date": "d1"}}

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

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -v`
Expected: FAIL（`send_notification_email`が`mail_check`モジュールに存在しない、`append_log`/`CSV_FIELDNAMES`が見つからない等）

- [ ] **Step 3: mail_check.py を書き換える**

まず、ファイル冒頭のimport部分（1〜16行目）を次の内容に置き換える（`import csv`を削除し、`notifier`からのimportを追加）。

```python
"""IMAPで新着メールをチェックし、件名キーワードに該当したメールをAI判定して通知メールを送る。"""
import email
import imaplib
import json
import logging
import os
import re
from datetime import datetime
from email.header import decode_header

from ai_judge import judge_urgency
from notifier import send_notification_email

CONFIG_PATH = "config.json"
PROCESSED_UIDS_PATH = "processed_uids.json"
LOG_FILE_PATH = "mail_check.log"
```

次に、`LOG_CSV_PATH`・`CSV_FIELDNAMES`・`append_log`関数（元の44〜65行目、`match_keywords`関数の直後から`connect_imap`関数の直前まで）を**削除**する。

最後に、`main()`関数を次の内容に置き換える。

```python
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
        matches = []

        for uid_str in new_uids:
            try:
                uid = uid_str.encode()
                header = fetch_header(conn, uid)
                matched = match_keywords(header["subject"], config["keywords"])

                if matched:
                    body = fetch_body(conn, uid)
                    judgement = judge_urgency(
                        header["subject"], body, config["anthropic_api_key"]
                    )
                    matches.append({
                        "差出人": header["from"],
                        "件名": header["subject"],
                        "ヒットキーワード": "・".join(matched),
                        "緊急度": judgement["urgency"],
                        "返信要否": judgement["reply_needed"],
                        "AI判断理由": judgement["reason"],
                    })
            except Exception as error:
                logger.error(f"メール処理に失敗しました: uid={uid_str}: {error}")
            finally:
                processed.add(uid_str)

        save_processed_uids(processed)

        if matches:
            try:
                send_notification_email(matches, config)
                logger.info(f"通知メール送信完了: {len(matches)}件")
            except Exception as error:
                logger.error(f"通知メール送信に失敗しました: {error}")
                for match in matches:
                    logger.error(f"未通知の検知結果: {match}")

        logger.info(
            f"実行完了: 新着{len(new_uids)}件中{len(matches)}件がキーワードに該当しました"
        )
    finally:
        conn.logout()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd "メール処理" && pytest test_mail_check.py -v`
Expected: PASS（全件成功。`test_append_log_*`は削除済みのため実行されない）

- [ ] **Step 5: フルスイートを実行して回帰がないことを確認する**

Run: `cd "メール処理" && pytest -v`
Expected: PASS（`test_notifier.py`・`test_ai_judge.py`・`test_mail_check.py`すべて成功）

- [ ] **Step 6: Commit**

```bash
git add メール処理/mail_check.py メール処理/test_mail_check.py
git commit -m "feat(メール処理): 検知結果の記録先をCSVからメール通知に変更"
```

---

### Task 3: 後片付け（.gitignore・使い方.md の更新）

**Files:**
- Modify: `メール処理/.gitignore`
- Modify: `メール処理/使い方.md`

**Interfaces:**
- Consumes: Task 1・Task 2の変更内容（ドキュメントに反映するため）

- [ ] **Step 1: .gitignore から mail_check_log.csv の行を削除する**

`メール処理/.gitignore`の現在の内容:
```
config.json
processed_uids.json
mail_check_log.csv
__pycache__/
*.pyc
.pytest_cache/
```

これを次の内容に置き換える（`mail_check_log.csv`の行を削除）。

```
config.json
processed_uids.json
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 2: 使い方.md を更新する**

`メール処理/使い方.md`内の「## 3. 結果の見方」セクション（`### mail_check_log.csv（検知結果ログ）`の見出しとその表を含む部分）を、次の内容に置き換える。

```markdown
## 3. 結果の見方

### 通知メール

キーワードに該当したメールがあった場合、チェック実行のたびに**まとめて1通**、
`config.json`の`notify_to`に設定したアドレスへ通知メールが届きます。該当メールが
1件もない場合は、メールは送信されません。

メール本文には、該当したメールごとに以下の内容が記載されます。

- 差出人
- 件名
- ヒットキーワード
- 緊急度（AIが判定: 高・中・低）
- 返信要否（AIが判定: 要・不要）
- 理由（AIが判定した根拠）

### `mail_check.log`（実行ログ）

接続エラーや、通知メール送信に失敗した場合の詳細（該当メールの件名・緊急度等）が
記録されます。普段は見なくて大丈夫です。
```

また、「## 2. 初回だけ行う準備」の「準備1」セクション内、`config.json`の例を次の内容に置き換える（`smtp_host`・`smtp_port`・`notify_to`を追記）。

```json
{
  "imap_host": "okashinodepart.net",
  "imap_port": 143,
  "use_ssl": false,
  "user": "tenri@okashinodepart.net",
  "password": "ここにメールパスワードを入力してください",
  "keywords": ["オンライン集計", "締め切り", "至急"],
  "anthropic_api_key": "ここにClaude APIキーを入力してください",
  "smtp_host": "okashinodepart.net",
  "smtp_port": 587,
  "notify_to": "ここに通知を受け取りたいメールアドレスを入力してください"
}
```

その直後の説明文（`- password: ...` / `- anthropic_api_key: ...`の箇条書き）に、以下を追記する。

```markdown
- `notify_to`: 検知結果の通知メールを受け取りたいメールアドレス
```

- [ ] **Step 3: Commit**

```bash
git add メール処理/.gitignore メール処理/使い方.md
git commit -m "docs(メール処理): 通知メール方式への変更をドキュメントに反映"
```

---

## Self-Review Notes

- **仕様カバレッジ:** 設計書の「config.jsonの追加項目」はTask 3の使い方.md更新でユーザー向けに案内（実際のconfig.json編集はユーザー自身が行うため、コードタスクの対象外）。「notifier.pyの設計」はTask 1で実装。「main()の変更」「エラー処理」（送信失敗時のフォールバックログ含む）はTask 2で実装・テスト。「テスト方針」（CSV関連テスト削除、SMTPのモック化）はTask 1・2で実施。
- **プレースホルダー確認:** 各ステップに実コードを記載済み。TODO/TBD等は無し。
- **型・シグネチャの一貫性:** `send_notification_email(matches, config)`の呼び出し（Task 2の`main()`内）はTask 1の定義と一致。`matches`の各要素が持つキー（`差出人`, `件名`, `ヒットキーワード`, `緊急度`, `返信要否`, `AI判断理由`）は、Task 1の`build_email_body`とTask 2の`main()`内での組み立てで統一されている。
- **既知の注意点:** `_setup_logger()`はモジュール単位のロガーシングルトンのため、同一pytestプロセス内で複数の`test_main_*`が実行されると、2件目以降のテストで`FileHandler`が最初のテストの`tmp_path`を指したままになる（新しいテストでは`if not logger.handlers`のガードにより再作成されない）。この計画のログ検証テスト（`test_main_logs_details_when_notification_send_fails`）はこの問題を回避するため、ファイルではなく`caplog`フィクスチャでロガー出力を直接検証している。
