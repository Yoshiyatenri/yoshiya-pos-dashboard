"""IMAPで新着メールをチェックし、件名キーワードに該当したメールをAI判定してログに残す。"""
import csv
import imaplib
import json
import os

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
