"""SHUFOO掲載用CSVと画像ZIPを対話形式で生成する。"""
import csv
import json
import zipfile
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


CSV_HEADER = [
    "チラシ入稿ID", "Shufoo!店舗ID(必須)", "先方店舗名",
    "掲載開始日時(必須)", "掲載終了日時(必須)", "チラシタイトル(必須)",
    "チラシ画像ファイル（１ページ目）", "チラシ画像ファイル（２ページ目）",
    "チラシ画像ファイル（３ページ目）", "チラシ画像ファイル（４ページ目）",
    "チラシ画像ファイル（５ページ目）", "チラシ画像ファイル（６ページ目）",
    "チラシ画像ファイル（７ページ目）", "チラシ画像ファイル（８ページ目）",
    "チラシ画像ファイル（９ページ目）", "チラシ画像ファイル（１０ページ目）",
    "チラシ画像ファイル（１１ページ目）", "チラシ画像ファイル（１２ページ目）",
    "チラシ画像ファイル（１３ページ目）", "チラシ画像ファイル（１４ページ目）",
    "チラシ画像ファイル（１５ページ目）", "チラシ画像ファイル（１６ページ目）",
    "ページスタイル", "ページの開き方", "掲載期間表示有無",
]


def resolve_image_filename(store, default_image, overrides):
    """店舗ごとの画像ファイル名を決定する（例外指定があればそちらを優先）。"""
    return overrides.get(store["store_id"], default_image)


def build_csv_rows(stores, start_dt, end_dt, title, default_image, overrides):
    """店舗マスターと入力値から、CSVの各行（25要素のリスト）を組み立てる。"""
    start_text = format_datetime(start_dt)
    end_text = format_datetime(end_dt)
    rows = []
    for store in stores:
        image = resolve_image_filename(store, default_image, overrides)
        row = (
            [store["entry_id"], store["store_id"], store["store_name"],
             start_text, end_text, title, image]
            + [""] * 15
            + ["1", "", "N"]
        )
        rows.append(row)
    return rows


def write_csv(rows, csv_path):
    """CSVをcp932エンコードで書き出す（既存ファイルは上書き）。"""
    with open(csv_path, "w", encoding="cp932", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)


def collect_used_images(rows):
    """CSVの各行から、1ページ目の画像ファイル名を重複除去して集める。"""
    return sorted({row[6] for row in rows if row[6]})


def check_images_exist(image_filenames, folder):
    """画像フォルダ内に実在するかを確認し、(存在するファイル一覧, 存在しないファイル一覧)を返す。"""
    existing, missing = [], []
    for name in image_filenames:
        if (folder / name).exists():
            existing.append(name)
        else:
            missing.append(name)
    return existing, missing


def write_zip(image_filenames, folder, zip_path):
    """指定した画像ファイルをZIPにまとめる（既存ファイルは上書き）。"""
    with zipfile.ZipFile(zip_path, "w") as z:
        for name in image_filenames:
            z.write(folder / name, arcname=name)
