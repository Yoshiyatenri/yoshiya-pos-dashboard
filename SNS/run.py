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
API_KEY_PLACEHOLDER = "ここにClaude APIキーを入力してください"


def main():
    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"config.jsonが見つかりません: {CONFIG_PATH}")
        print("SNSフォルダー内にconfig.jsonを作成してください。")
        return
    except json.JSONDecodeError as error:
        print(f"config.jsonの内容が正しいJSON形式ではありません: {error}")
        return

    today = date.today().strftime("%Y%m%d")
    csv_path = DATA_DIR / f"raw_{today}.csv"
    report_path = REPORTS_DIR / f"{today}.xlsx"

    print("指定されたURLから投稿データを収集しています...")
    records = collect_all(config)
    save_csv(records, csv_path)
    print(f"{len(records)}件の投稿データを取得しました: {csv_path}")

    records = load_records(csv_path)
    summary = summarize(records)

    api_key = config.get("anthropic_api_key", "")
    if not records:
        print("投稿データが1件も取得できなかったため、企画案の生成をスキップします。")
        plan_ideas = []
    elif not api_key or api_key == API_KEY_PLACEHOLDER:
        print("Claude APIキーが設定されていないため、企画案の生成をスキップします。")
        plan_ideas = []
    else:
        print("Claude APIで投稿企画案を生成しています...")
        plan_ideas = generate_plan_ideas(summary, api_key)

    create_report(summary, plan_ideas, str(report_path))
    print(f"レポートを出力しました: {report_path}")


if __name__ == "__main__":
    main()
