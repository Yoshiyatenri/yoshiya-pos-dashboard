"""SHUFOO掲載用CSVと画像ZIPを対話形式で生成する。"""
import json
from datetime import date, datetime, time, timedelta


def load_config(config_path):
    """config.jsonを読み込む。"""
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def parse_date(text, default_year):
    """日付文字列（M/D または YYYY/M/D）をdateに変換する。"""
    parts = text.strip().split("/")
    if len(parts) == 2:
        month, day = int(parts[0]), int(parts[1])
        year = default_year
    elif len(parts) == 3:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        raise ValueError(f"日付の形式が正しくありません: {text}")
    return date(year, month, day)


def compute_period(start_date, end_date):
    """掲載開始日時（開始日の前日19:00）と掲載終了日時（終了日15:00）を計算する。"""
    start_dt = datetime.combine(start_date - timedelta(days=1), time(19, 0))
    end_dt = datetime.combine(end_date, time(15, 0))
    return start_dt, end_dt


def format_datetime(dt):
    """日時をCSV用の文字列（例: 2026/7/9 19:00）に変換する。"""
    return f"{dt.year}/{dt.month}/{dt.day} {dt.hour}:{dt.minute:02d}"
