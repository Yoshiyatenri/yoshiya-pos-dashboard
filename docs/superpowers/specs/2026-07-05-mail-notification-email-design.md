# CSV出力→メール通知への切り替え 設計書

作成日: 2026-07-05

## 背景・目的

既存の「メール件名キーワード検知＋AI緊急度判定」ツール（`メール処理/`）は、検知結果を
`mail_check_log.csv`に記録する仕様だった。運用の結果、CSVを都度確認する手間があるため、
検知結果を指定メールアドレスへ直接通知する方式に変更する。

CSV出力は廃止し、メール通知のみに一本化する。

## 変更の概要

| 項目 | 変更前 | 変更後 |
|---|---|---|
| 検知結果の記録先 | `mail_check_log.csv` | 指定メールアドレスへの通知メール |
| 通知タイミング | 該当メールごとに1行追記 | 1回の実行で見つかった分をまとめて1通送信 |
| 該当0件の場合 | 何もしない | 何もしない（変更なし） |
| 送信失敗時 | （該当なし） | `mail_check.log`に詳細（件名・緊急度等）を記録 |

## config.jsonの追加項目

既存の項目（`imap_host`, `imap_port`, `use_ssl`, `user`, `password`, `keywords`,
`anthropic_api_key`）に加えて、以下を追加する。

```json
{
  "smtp_host": "okashinodepart.net",
  "smtp_port": 587,
  "notify_to": "hanakiti0811@gmail.com"
}
```

- `smtp_host` / `smtp_port`: SMTP送信サーバー（ポート587への接続確認済み、STARTTLS想定）
- `notify_to`: 通知メールの送信先アドレス
- SMTP認証は既存の`user`/`password`（IMAPと同じ`tenri@okashinodepart.net`アカウント）を流用する

## ファイル構成の変更

| ファイル | 変更内容 |
|---|---|
| `メール処理/notifier.py` | **新規作成**。通知メールの組み立て・送信を担当 |
| `メール処理/test_notifier.py` | **新規作成**。`notifier.py`のテスト |
| `メール処理/mail_check.py` | `append_log`・`CSV_FIELDNAMES`・`LOG_CSV_PATH`を削除し、`main()`から`notifier.py`を呼び出すように変更 |
| `メール処理/test_mail_check.py` | CSV関連テストを削除し、メール送信呼び出しを検証するテストに変更 |
| `メール処理/.gitignore` | `mail_check_log.csv`の行を削除 |
| `メール処理/使い方.md` | CSV確認の説明をメール通知の説明に更新 |

## notifier.pyの設計

### `build_email_body(matches: list[dict]) -> str`

検知したメールの情報（辞書のリスト）から、まとめて1通分の本文テキストを組み立てる。
1件の辞書は、旧CSV実装（`CSV_FIELDNAMES`）と同じ日本語キーを持つ想定とする
（`main()`側で不要な変換層を作らないため、キー名は変更しない）。

```python
{
    "差出人": "...",
    "件名": "...",
    "ヒットキーワード": "至急・締め切り",  # "・"区切りの文字列
    "緊急度": "高",
    "返信要否": "要",
    "AI判断理由": "...",
}
```

本文は「1件ごとに区切り線を挟んだテキストブロック」の形式とする。

```
以下のキーワード該当メールを検知しました（2件）。

----------------------------------------
差出人: 本部 <honbu@example.com>
件名: 至急対応願います
ヒットキーワード: 至急
緊急度: 高
返信要否: 要
理由: 締め切りが本日のため
----------------------------------------
差出人: ...
...
```

### `send_notification_email(matches, config) -> None`

- `smtplib.SMTP(config["smtp_host"], config["smtp_port"])`で接続
- `starttls()` → `login(config["user"], config["password"])`
- 件名は `f"メールチェック結果: {len(matches)}件検知"`
- 本文は`build_email_body(matches)`
- 送信先は`config["notify_to"]`、送信元は`config["user"]`
- 送信に失敗した場合は例外をそのまま呼び出し元（`main()`）に伝播させる（`main()`側でログに記録する）

## main()の変更

現在の実装（`メール処理/mail_check.py`の`main()`）から、以下のように変更する。

- ループ開始前に`matches = []`を用意する
- キーワードに該当したメールについて、これまで`append_log(...)`を呼んでいた箇所を、
  `matches`リストへの追加に置き換える
- ループ終了後（`save_processed_uids(processed)`の前後どちらでもよいが、通知失敗時も
  UIDの処理済み登録は行うため、`save_processed_uids`より後に配置する）:
  - `matches`が空でなければ`send_notification_email(matches, config)`を呼ぶ
  - 送信が成功すればログに「通知メール送信完了（N件）」と記録
  - 送信が例外を投げた場合は、`matches`の内容（件名・緊急度など）を含めて
    `mail_check.log`に詳細記録する（**フォールバックであり代替手段ではない**：
    次回実行時にこのメールが再送されるわけではない）

既存の「メール1件の処理失敗が全体を止めない」仕組み（前回の修正）はそのまま維持する。
1件のメール取得・AI判定に失敗しても、他のメールの処理と通知送信は継続される。

## エラー処理

- IMAP接続失敗: 既存通り（ログ記録して終了、`processed_uids.json`は更新しない）
- 1件のメール取得・AI判定失敗: 既存通り（ログ記録してスキップ、UIDは処理済みとして記録）
- 通知メール送信失敗: `matches`の詳細を`mail_check.log`に記録する。この場合でも
  `processed_uids.json`の更新（UIDを処理済みにする）は行う（再実行時に同じメールを
  重複して検知しないため）

## テスト方針

- `notifier.py`: `smtplib.SMTP`を`unittest.mock.MagicMock`で差し替え、
  `starttls()`・`login()`・`send_message()`（またはそれに準ずるメソッド）が正しい引数で
  呼ばれることを検証する。実際のSMTPサーバーへは接続しない
- `mail_check.py`の`main()`: `notifier.send_notification_email`を
  `unittest.mock.patch`で差し替え、該当メールがあった場合に正しい内容の`matches`
  リストで呼ばれること、該当0件の場合は呼ばれないことを検証する
- CSV関連の既存テスト（`test_append_log_*`）は削除する

## 移行時の注意

- `mail_check_log.csv`は今後生成されなくなる。既存のファイルが残っていても実害はないが、
  運用上は不要になるため削除して構わない
- `config.json`に`smtp_host`・`smtp_port`・`notify_to`を追加入力する必要がある
  （実際の値は既に確認済み: `okashinodepart.net` / `587` / `hanakiti0811@gmail.com`）
