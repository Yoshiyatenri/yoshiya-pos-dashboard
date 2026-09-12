"""
指定期間の取引レポートを連続ダウンロード＆取り込みする

実行方法:
  python download_visitors_range.py 20260801 20260831
"""
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"import_{datetime.now():%Y%m}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

import download
import import_visitors


def run_range(start_str: str, end_str: str):
    start = datetime.strptime(start_str, "%Y%m%d")
    end   = datetime.strptime(end_str,   "%Y%m%d")

    total_days = (end - start).days + 1
    log.info(f"=== {start.strftime('%Y/%m/%d')} 〜 {end.strftime('%Y/%m/%d')} ({total_days}日分) の取り込み開始 ===")

    success = 0
    failed = []

    d = start
    while d <= end:
        date_str = d.strftime("%Y%m%d")
        log.info(f"--- [{success+1+len(failed)}/{total_days}] {d.strftime('%Y/%m/%d')} ---")

        path = download.run_visitors(d)
        if path:
            count = import_visitors.run(date_str)
            log.info(f"  → {d.strftime('%Y/%m/%d')}: 来店客数 {count}件追加")
            success += 1
        else:
            log.warning(f"  → {d.strftime('%Y/%m/%d')}: ダウンロード失敗。スキップ。")
            failed.append(date_str)

        d += timedelta(days=1)

    log.info("=" * 50)
    log.info(f"完了: {success}日成功, {len(failed)}日失敗")
    if failed:
        log.warning(f"失敗日付: {failed}")
    log.info("=" * 50)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("使い方: python download_visitors_range.py 20260801 20260831")
        sys.exit(1)
    run_range(sys.argv[1], sys.argv[2])
