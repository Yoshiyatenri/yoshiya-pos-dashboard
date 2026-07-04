"""IMAPで新着メールをチェックし、件名キーワードに該当したメールをAI判定してログに残す。"""
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
