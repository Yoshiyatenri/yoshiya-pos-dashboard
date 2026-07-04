"""SNS投稿分析ツールのエントリーポイント。手動実行用。"""
import json
from datetime import date
from pathlib import Path

from scraper import collect_all, save_csv
from analyzer import load_records, summarize
from planner import generate_plan_ideas
from report import create_report

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = DATA_DIR / "reports"


def main():
    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    today = date.today().strftime("%Y%m%d")
    csv_path = DATA_DIR / f"raw_{today}.csv"
    report_path = REPORTS_DIR / f"{today}.xlsx"

    print("指定されたURLから投稿データを収集しています...")
    records = collect_all(config)
    save_csv(records, csv_path)
    print(f"{len(records)}件の投稿データを取得しました: {csv_path}")

    records = load_records(csv_path)
    summary = summarize(records)

    print("Claude APIで投稿企画案を生成しています...")
    plan_ideas = generate_plan_ideas(summary, config["anthropic_api_key"])

    create_report(summary, plan_ideas, str(report_path))
    print(f"レポートを出力しました: {report_path}")


if __name__ == "__main__":
    main()
