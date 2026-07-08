# 通知メールの検索条件に日付条件を追加 設計書

作成日: 2026-07-08

## 背景・目的

既存の「メール件名キーワード検知＋AI緊急度判定」ツール（`メール処理/`）は、件名にキーワード
（「オンライン集計」「締め切り」「至急」など）が含まれるメールのみを通知対象としていた。

キーワードを含まないが、件名や本文に「本日」または「明日」の日付が記載されている
（＝当日・翌日締め切りを示唆する）メールも見落とさないよう、日付による判定条件を追加する。

## 変更の概要

| 項目 | 変更前 | 変更後 |
|---|---|---|
| キーワード検索範囲 | 件名のみ | 件名＋本文 |
| 本文の取得タイミング | キーワード一致後にのみ取得 | 新着メール全件で取得 |
| 受信日時の取得 | 取得していない | IMAPのINTERNALDATE（サーバー受信日時）を取得 |
| マッチ条件 | キーワード一致のみ | キーワード一致 **または** 日付一致 |
| 通知の「ヒットキーワード」欄 | キーワード文字列 | キーワード一致時はキーワード。日付一致のみの場合は`日付(7/10)`のように検出した日付文字列を表示 |

## 日付条件の仕様

メールの受信日（IMAPサーバーが記録したINTERNALDATE）を基準に、以下2つの日付を対象とする。

- 受信日当日
- 受信日の翌日（月またぎ・年またぎも`datetime.date + timedelta(days=1)`で自動的に処理される）

それぞれの日付について、以下2つの表記形式のいずれかが件名または本文に含まれていれば
日付一致とする。

- `X月Y日`形式（例: `7月10日`）— ゼロ埋めなし
- `X/Y`形式（例: `7/10`）— ゼロ埋めなし

`X/Y`形式は数字の部分一致による誤検出を防ぐため、前後が数字で続かないことを確認する
（例: 受信日が7/1の場合、本文中の「7/10」に部分一致して誤検出しないようにする）。
`X月Y日`形式は「月」「日」という漢字が区切りとなるため、この誤検出は起こらない。

## ファイル構成の変更

| ファイル | 変更内容 |
|---|---|
| `メール処理/mail_check.py` | `match_keywords`の対象を件名＋本文に変更。新規`match_dates`関数を追加。`fetch_header`がINTERNALDATEも取得するように変更。`main()`のマッチ判定ロジックを変更 |
| `メール処理/test_mail_check.py` | 上記変更に対応するテストを追加・修正 |
| `メール処理/使い方.md` | 検索条件の説明を更新 |

## mail_check.pyの設計

### `match_keywords(text, keywords) -> list[str]`

現状は件名文字列のみを受け取っていたが、件名と本文を結合したテキストを受け取るように
変更する（呼び出し側で結合する）。ロジック自体（部分一致でキーワードのリストを返す）は
変更しない。

### `match_dates(text, received_date) -> list[str]`

`received_date`（`datetime.date`）と`received_date + timedelta(days=1)`のそれぞれについて、
`X月Y日`形式・`X/Y`形式の文字列を生成し、`text`中に含まれるか判定する。
一致した日付文字列（`X/Y`形式で統一。例: `["7/10"]`）をリストで返す。一致がなければ空リスト。

```python
import re
from datetime import timedelta

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

### `fetch_header`の変更

IMAPフェッチコマンドに`INTERNALDATE`を追加し、`imaplib.Internaldate2tuple`で
`datetime.date`に変換して返り値に含める。

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

`imaplib.Internaldate2tuple`は応答の中からINTERNALDATE部分を自分で正規表現抽出するため、
`raw_response[0]`（`b'1 (INTERNALDATE "05-Jul-2026 09:12:34 +0900" BODY[...] {123}'`のような
バイト列）をそのまま渡せばよい。

### `main()`の変更

新着メール全件について、キーワード判定・日付判定の両方に必要な本文を先に取得する。
判定はキーワード一致 **または** 日付一致のOR条件とする。

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

既存の「メール1件の処理失敗が全体を止めない」仕組み（try/except/finally）はそのまま維持する。

## エラー処理

- IMAP接続失敗・1件のメール処理失敗・通知メール送信失敗: 既存通り
- INTERNALDATEの取得・パースに失敗した場合も、そのメール1件の処理失敗として扱い、
  他のメールの処理は継続する（既存のtry/except/finallyの中で発生するため、追加対応不要）

## テスト方針

- `match_keywords`: 件名のみ一致、本文のみ一致、両方一致、どちらも一致しない場合をテスト
- `match_dates`: 受信日一致、翌日一致（月またぎを含む）、`X月Y日`形式、`X/Y`形式、
  部分一致による誤検出がないこと（例: 受信日7/1のとき本文に「7/10」だけがある場合は
  一致しないこと）をテスト
- `fetch_header`: INTERNALDATEを含むIMAPレスポンスをモックし、`received_date`が
  正しく`datetime.date`に変換されることをテスト
- `main()`: キーワードのみ一致・日付のみ一致・両方一致・どちらも一致しない場合で
  `matches`の内容（特に「ヒットキーワード」欄の表示）が正しいことをテスト

## 移行時の注意

- 本文を新着メール全件で取得するようになるため、IMAP通信量がこれまでよりやや増える。
  ただしこのメールボックスの新着件数は2時間あたり数件程度であり、実用上の影響はない
