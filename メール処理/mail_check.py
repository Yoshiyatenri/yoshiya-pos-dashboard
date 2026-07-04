"""IMAPで新着メールをチェックし、件名キーワードに該当したメールをAI判定してログに残す。"""
import json

CONFIG_PATH = "config.json"


def load_config(path=CONFIG_PATH):
    """config.jsonを読み込んで辞書として返す。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
