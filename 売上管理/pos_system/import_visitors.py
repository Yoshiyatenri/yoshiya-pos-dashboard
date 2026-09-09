"""
取引レポートCSVをvisitorsテーブルに取り込む

対象ファイルパターン:
  「店舗：6 取引レポート (レジ別) 【ＣＳＶ】  [2026.09.08 ～ 2026.09.08].csv」
  ファイル名から店舗コードと日付を取得。
  CSVの「客数」行の「合計」列（2列目）を来店客数として使用。

実行方法:
  python import_visitors.py                     # downloadsフォルダ内を全件処理
  python import_visitors.py downloads/店舗：6*.csv  # 特定ファイルを指定
"""
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras
    _psycopg2_ok = True
except ImportError:
    _psycopg2_ok = False

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
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

CREATE_SQLITE = """
CREATE TABLE IF NOT EXISTS visitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pos_date TEXT,
    store_code INTEGER,
    store_name TEXT,
    visitors_count INTEGER,
    UNIQUE(pos_date, store_code)
)
"""

CREATE_PG = CREATE_SQLITE.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")

# ファイル名パターン例: 「店舗：6 取引レポート (レジ別) 【ＣＳＶ】  [2026.09.08 ～ 2026.09.08].csv」
FILENAME_RE = re.compile(r'店舗：(\d+).*?\[(\d{4})\.(\d{2})\.(\d{2})')
STORE_NAME_RE = re.compile(r'^\d+:(.+?)\[')


def _cfg():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _use_pg() -> bool:
    url = _cfg().get("db_url", "")
    return _psycopg2_ok and bool(url) and "XXXXXXXXXX" not in url


def parse_visitors_csv(csv_path: Path) -> tuple[str, int, str, int] | None:
    """
    取引レポートCSVをパースして (pos_date, store_code, store_name, visitors_count) を返す。
    パース失敗時はNoneを返す。
    """
    m = FILENAME_RE.search(csv_path.name)
    if not m:
        log.warning(f"ファイル名から日付・店舗コードを取得できません: {csv_path.name}")
        return None

    store_code = int(m.group(1))
    pos_date = f"{m.group(2)}-{m.group(3)}-{m.group(4)}"

    try:
        raw = csv_path.read_bytes()
        text = raw.decode("shift_jis", errors="replace")
    except Exception as e:
        log.error(f"ファイル読み込みエラー: {csv_path.name} → {e}")
        return None

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # ヘッダーから店舗名を取得（3列目: 「6:店舗名[レジ番号]」形式）
    store_name = ""
    if lines:
        header_cols = lines[0].split(",")
        if len(header_cols) >= 3:
            sm = STORE_NAME_RE.match(header_cols[2].strip())
            if sm:
                store_name = sm.group(1).strip()

    # 「客数」行の合計列（2列目）を取得
    visitors_count = None
    for line in lines[1:]:
        cols = line.split(",")
        if cols and cols[0].strip() == "客数":
            try:
                visitors_count = int(cols[1].strip())
            except (ValueError, IndexError):
                log.warning(f"客数の値が取得できません: {line!r}")
                return None
            break

    if visitors_count is None:
        log.warning(f"「客数」行が見つかりません: {csv_path.name}")
        return None

    return pos_date, store_code, store_name, visitors_count


def import_file(csv_path: Path) -> bool:
    result = parse_visitors_csv(csv_path)
    if result is None:
        return False

    pos_date, store_code, store_name, visitors_count = result
    log.info(f"{csv_path.name} → {pos_date} 店舗{store_code}({store_name}) 客数={visitors_count}")

    if _use_pg():
        return _insert_pg(pos_date, store_code, store_name, visitors_count)
    else:
        return _insert_sqlite(pos_date, store_code, store_name, visitors_count)


def _insert_sqlite(pos_date, store_code, store_name, visitors_count) -> bool:
    cfg = _cfg()
    db_path = BASE_DIR / cfg.get("db_path_sqlite", "pos_data.db")
    con = sqlite3.connect(str(db_path))
    con.execute(CREATE_SQLITE)
    con.commit()
    before = con.total_changes
    con.execute(
        "INSERT OR IGNORE INTO visitors (pos_date, store_code, store_name, visitors_count) VALUES (?, ?, ?, ?)",
        (pos_date, store_code, store_name, visitors_count),
    )
    con.commit()
    inserted = con.total_changes > before
    con.close()
    if inserted:
        log.info(f"  → 追加完了（SQLite）")
    else:
        log.info(f"  → 既存データのためスキップ（SQLite）")
    return True


def _insert_pg(pos_date, store_code, store_name, visitors_count) -> bool:
    cfg = _cfg()
    con = psycopg2.connect(cfg["db_url"])
    cur = con.cursor()
    cur.execute(CREATE_PG)
    cur.execute(
        "INSERT INTO visitors (pos_date, store_code, store_name, visitors_count) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (pos_date, store_code) DO NOTHING",
        (pos_date, store_code, store_name, visitors_count),
    )
    con.commit()
    cur.close()
    con.close()
    log.info(f"  → 完了（Supabase）")
    return True


def run(paths: list[Path] | None = None) -> int:
    if paths is None:
        cfg = _cfg()
        dl_dir = BASE_DIR / cfg.get("download_dir", "downloads")
        # 取引レポートCSVのみ対象（ファイル名に「取引レポート」を含む）
        paths = list(dl_dir.glob("*取引レポート*.csv"))
        if not paths:
            log.info("取引レポートCSVが見つかりませんでした")
            return 0

    success = 0
    for p in sorted(paths):
        if import_file(p):
            success += 1

    log.info(f"=== 処理完了: {success}/{len(paths)} 件 ===")
    return success


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_paths = [Path(p) for p in sys.argv[1:]]
    else:
        target_paths = None
    run(target_paths)
