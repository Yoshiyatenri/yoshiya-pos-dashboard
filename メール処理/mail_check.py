"""IMAPで新着メールをチェックし、件名キーワードに該当したメールをAI判定して通知メールを送る。"""
import email
import imaplib
import json
import logging
import os
import re
from datetime import date, timedelta
from email.header import decode_header

from ai_judge import judge_urgency
from notifier import send_notification_email

CONFIG_PATH = "config.json"
PROCESSED_UIDS_PATH = "processed_uids.json"
LOG_FILE_PATH = "mail_check.log"


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


def match_keywords(text, keywords):
    """件名+本文の結合テキストに含まれるキーワードのリストを返す（部分一致）。"""
    return [kw for kw in keywords if kw in text]


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
        matches = []

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
