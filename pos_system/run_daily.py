"""
毎日の自動実行スクリプト
1. DBの最新日付を確認し、未取得の日付を列挙
2. 各日付のCSVをダウンロード
3. SQLiteデータベースに取り込む
タスクスケジューラから呼び出される（07:00 StartWhenAvailable=True）
"""
import json
import logging
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"daily_{datetime.now():%Y%m}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def find_missing_dates() -> list[date]:
    """昨日までのうち、CSVダウンロードが未完了の日付リストを返す"""
    cfg = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
    download_dir = (BASE_DIR / cfg["download_dir"]).resolve()
    db_path = (BASE_DIR / cfg.get("db_path_sqlite", "pos_data.db")).resolve()

    yesterday = datetime.now().date() - timedelta(days=1)

    # DBの最新日付の翌日から確認する
    start_date = yesterday  # デフォルト: 昨日のみ
    if db_path.exists():
        con = sqlite3.connect(str(db_path))
        row = con.execute("SELECT MAX(pos_date) FROM sales").fetchone()
        con.close()
        if row and row[0]:
            start_date = datetime.strptime(row[0], "%Y-%m-%d").date() + timedelta(days=1)

    # start_date〜昨日のうち、CSVファイルが存在しない日を列挙
    missing = []
    current = start_date
    while current <= yesterday:
        csv_file = download_dir / f"{current.strftime('%Y%m%d')}.csv"
        if not csv_file.exists():
            missing.append(current)
        current += timedelta(days=1)

    return missing


def main():
    log.info("=" * 50)
    log.info("日次処理 開始")
    log.info("=" * 50)

    import download
    import import_db

    missing_dates = find_missing_dates()

    if not missing_dates:
        log.info("未取得の日付なし。処理完了。")
        return

    log.info(f"未取得の日付: {len(missing_dates)}日分 ({missing_dates[0]} 〜 {missing_dates[-1]})")

    total_inserted = 0
    failed_dates = []

    for d in missing_dates:
        log.info(f"--- {d.strftime('%Y/%m/%d')} の処理開始 ---")

        csv_path = download.run(datetime.combine(d, datetime.min.time()))
        if not csv_path:
            log.error(f"{d} のCSVダウンロード失敗。スキップします。")
            failed_dates.append(d)
            continue

        inserted = import_db.import_csv(csv_path)
        total_inserted += inserted
        log.info(f"{d}: {inserted}件追加")

    log.info("=" * 50)
    if failed_dates:
        log.warning(f"失敗した日付: {[str(d) for d in failed_dates]}")
    log.info(f"日次処理 完了: 計{total_inserted}件追加")
    log.info("=" * 50)

    if failed_dates:
        sys.exit(1)


if __name__ == "__main__":
    main()
