"""SHUFOO掲載用CSVと画像ZIPを対話形式で生成する。"""
import json


def load_config(config_path):
    """config.jsonを読み込む。"""
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)
