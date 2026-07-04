"""IMAPで新着メールをチェックし、件名キーワードに該当したメールをAI判定してログに残す。"""
import csv
import email
import imaplib
import json
import os
import re
from email.header import decode_header

CONFIG_PATH = "config.json"
PROCESSED_UIDS_PATH = "processed_uids.json"


def load_config(path=CONFIG_PATH):
    """config.jsonを読み込んで辞書として返す。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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


def match_keywords(subject, keywords):
    """件名に含まれるキーワードのリストを返す（部分一致）。"""
    return [kw for kw in keywords if kw in subject]


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
