"""TikTokの動画URLリストから投稿データを収集する。"""
import csv
import json
import re
import time
from datetime import datetime, timezone

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

STATE_SCRIPT_ID = "__UNIVERSAL_DATA_FOR_REHYDRATION__"


def build_driver(headless=True):
    """Edge用のSeleniumドライバーを作成する。"""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Edge(options=options)


def extract_hashtags(caption):
    """キャプション文字列からハッシュタグの一覧を抽出する。"""
    return re.findall(r"#(\S+)", caption)


def extract_item_from_html(html):
    """動画詳細ページのHTMLから投稿データ(itemStruct)を取り出す。

    TikTokはページ内の<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">タグに
    動画情報のJSONを埋め込んでいる。TikTok側の仕様変更でこの構造が変わった場合は
    実際のページのHTMLを確認してこの関数のキー参照（__DEFAULT_SCOPE__ ->
    webapp.video-detail -> itemInfo -> itemStruct）を修正すること。
    """
    match = re.search(
        rf'<script id="{STATE_SCRIPT_ID}"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if not match:
        return None
    data = json.loads(match.group(1))
    default_scope = data.get("__DEFAULT_SCOPE__", {})
    video_detail = default_scope.get("webapp.video-detail", {})
    return video_detail.get("itemInfo", {}).get("itemStruct")


def parse_item(item, url):
    """動画1件分の生データを、レポート用の形式に変換する。"""
    stats = item.get("stats", {})
    caption = item.get("desc", "")
    create_time = item.get("createTime")
    posted_at = ""
    if create_time:
        posted_at = datetime.fromtimestamp(
            int(create_time), tz=timezone.utc
        ).strftime("%Y-%m-%d")

    return {
        "url": url,
        "caption": caption,
        "hashtags": extract_hashtags(caption),
        "likes": int(stats.get("diggCount", 0)),
        "views": int(stats.get("playCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
        "shares": int(stats.get("shareCount", 0)),
        "posted_at": posted_at,
    }


def fetch_video(driver, url):
    """1件の動画URLにアクセスし、投稿データを取得する。"""
    driver.get(url)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(3)  # ページ内JSONの読み込み待ち
    item = extract_item_from_html(driver.page_source)
    if item is None:
        raise ValueError(f"動画データを取得できませんでした: {url}")
    return parse_item(item, url)


def collect_all(config):
    """設定ファイルの動画URL一覧すべてについてデータを取得し、まとめて返す。"""
    driver = build_driver(headless=config.get("headless", True))
    records = []
    try:
        for url in config["video_urls"]:
            print(f"{url} を取得中...")
            try:
                records.append(fetch_video(driver, url))
            except Exception as error:
                print(f"{url} の取得に失敗しました: {error}")
            time.sleep(config.get("wait_seconds_between_requests", 5))
    finally:
        driver.quit()
    return records


def save_csv(records, csv_path):
    """収集した投稿データをCSVファイルに保存する。"""
    fieldnames = [
        "url", "caption", "hashtags",
        "likes", "views", "comments", "shares", "posted_at",
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["hashtags"] = ";".join(row["hashtags"])
            writer.writerow(row)
