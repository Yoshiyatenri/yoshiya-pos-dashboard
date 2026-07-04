"""投稿データの集計ロジック。"""
import csv
from collections import Counter


def load_records(csv_path):
    """CSVファイルから投稿データを読み込み、dictのリストとして返す。"""
    records = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["hashtags"] = row["hashtags"].split(";") if row["hashtags"] else []
            row["likes"] = int(row["likes"])
            row["views"] = int(row["views"])
            row["comments"] = int(row["comments"])
            row["shares"] = int(row["shares"])
            records.append(row)
    return records


def top_hashtags(records, top_n=10):
    """出現回数が多いハッシュタグを多い順に返す。"""
    counter = Counter()
    for record in records:
        counter.update(record["hashtags"])
    return counter.most_common(top_n)


def top_videos(records, top_n=5, by="likes"):
    """指定した指標（likes/views/comments/shares）で上位の投稿を返す。"""
    return sorted(records, key=lambda r: r[by], reverse=True)[:top_n]


def summarize(records, top_n=10):
    """傾向データをまとめて辞書で返す。"""
    return {
        "video_count": len(records),
        "top_hashtags": top_hashtags(records, top_n),
        "top_videos_by_likes": top_videos(records, 5, "likes"),
    }
