"""TikTokのハッシュタグ・キーワード検索結果から投稿データを収集する。"""
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

SEARCH_URL = "https://www.tiktok.com/search/video?q={keyword}"
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


def extract_items_from_html(html):
    """検索結果ページのHTMLから投稿データのリストを取り出す。

    TikTokはページ内の<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">タグに
    検索結果のJSONを埋め込んでいる。TikTok側の仕様変更でこの構造が変わった場合は
    実際のページのHTMLを確認してこの関数を修正すること。
    """
    match = re.search(
        rf'<script id="{STATE_SCRIPT_ID}"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if not match:
        return []
    data = json.loads(match.group(1))
    default_scope = data.get("__DEFAULT_SCOPE__", {})
    search_data = default_scope.get("webapp.search-detail", {})
    return search_data.get("searchResult", {}).get("itemList", [])


def parse_item(raw_item, keyword):
    """検索結果1件分の生データを、レポート用の形式に変換する。"""
    item = raw_item.get("item", raw_item)
    video_id = item.get("id", "")
    author = item.get("author", {}).get("uniqueId", "")
    stats = item.get("stats", {})
    caption = item.get("desc", "")
    create_time = item.get("createTime")
    posted_at = ""
    if create_time:
        posted_at = datetime.fromtimestamp(
            int(create_time), tz=timezone.utc
        ).strftime("%Y-%m-%d")

    return {
        "url": f"https://www.tiktok.com/@{author}/video/{video_id}",
        "keyword": keyword,
        "caption": caption,
        "hashtags": extract_hashtags(caption),
        "likes": int(stats.get("diggCount", 0)),
        "views": int(stats.get("playCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
        "shares": int(stats.get("shareCount", 0)),
        "posted_at": posted_at,
    }


def search_keyword(driver, keyword, max_videos):
    """1つのキーワードでTikTok検索を行い、投稿データのリストを返す。"""
    driver.get(SEARCH_URL.format(keyword=keyword))
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(3)  # ページ内JSONの読み込み待ち
    raw_items = extract_items_from_html(driver.page_source)
    return [parse_item(raw, keyword) for raw in raw_items[:max_videos]]


def collect_all(config):
    """設定ファイルのキーワード一覧すべてについて検索し、投稿データをまとめて返す。"""
    driver = build_driver(headless=config.get("headless", True))
    all_records = []
    try:
        for keyword in config["keywords"]:
            print(f"「{keyword}」を検索中...")
            try:
                records = search_keyword(
                    driver, keyword, config["max_videos_per_keyword"]
                )
                all_records.extend(records)
            except Exception as error:
                print(f"「{keyword}」の取得に失敗しました: {error}")
            time.sleep(config.get("wait_seconds_between_requests", 5))
    finally:
        driver.quit()
    return all_records


def save_csv(records, csv_path):
    """収集した投稿データをCSVファイルに保存する。"""
    fieldnames = [
        "url", "keyword", "caption", "hashtags",
        "likes", "views", "comments", "shares", "posted_at",
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["hashtags"] = ";".join(row["hashtags"])
            writer.writerow(row)
