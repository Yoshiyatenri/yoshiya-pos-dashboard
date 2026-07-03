"""
ダウンロードしたCSVをDBに取り込む（SQLite / Supabase 自動切替）
- config.json の db_url が未設定 or XXXXXXXXXX → SQLite
- config.json の db_url が設定済み → Supabase
"""
import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd

try:
    import psycopg2
    import psycopg2.extras
    _psycopg2_ok = True
except ImportError:
    _psycopg2_ok = False

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
LOG_DIR = BASE_DIR / "logs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"import_{datetime.now():%Y%m}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

COLUMNS = [
    "pos_date", "store_code", "store_name",
    "mid_cat_code", "mid_cat_name", "small_cat_code", "small_cat_name",
    "class_code", "class_name", "cat_code", "cat_name",
    "liquor_cat_code", "liquor_cat_name",
    "plu_code", "plu_name", "spec", "volume", "alcohol",
    "master_cost", "master_price",
    "sales_amount", "sales_qty", "sales_customers", "gross_profit",
    "markdown_amount", "markdown_qty",
    "special_sales_amount", "special_discount_qty", "special_gross_profit",
    "plan_discount_amount", "last_sale_time", "weight",
    "return_amount", "return_qty", "return_bottle_amount", "return_bottle_qty",
]

CREATE_SQLITE = """
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pos_date TEXT, store_code INTEGER, store_name TEXT,
    mid_cat_code INTEGER, mid_cat_name TEXT, small_cat_code INTEGER, small_cat_name TEXT,
    class_code TEXT, class_name TEXT, cat_code INTEGER, cat_name TEXT,
    liquor_cat_code TEXT, liquor_cat_name TEXT,
    plu_code TEXT, plu_name TEXT, spec TEXT, volume TEXT, alcohol REAL,
    master_cost REAL, master_price REAL,
    sales_amount REAL, sales_qty INTEGER, sales_customers INTEGER, gross_profit REAL,
    markdown_amount REAL, markdown_qty INTEGER,
    special_sales_amount REAL, special_discount_qty INTEGER, special_gross_profit REAL,
    plan_discount_amount REAL, last_sale_time TEXT, weight REAL,
    return_amount REAL, return_qty INTEGER, return_bottle_amount REAL, return_bottle_qty INTEGER,
    UNIQUE(pos_date, store_code, plu_code)
)
"""

CREATE_PG = CREATE_SQLITE.replace(
    "INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY"
)


def _cfg():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _use_pg() -> bool:
    url = _cfg().get("db_url", "")
    return _psycopg2_ok and bool(url) and "XXXXXXXXXX" not in url


def import_csv(csv_path: str) -> int:
    log.info(f"取り込み開始: {csv_path}")
    df = pd.read_csv(csv_path, encoding="shift_jis", header=0, names=COLUMNS)
    df["pos_date"] = pd.to_datetime(df["pos_date"]).dt.strftime("%Y-%m-%d")
    df = df.where(pd.notna(df), None)
    rows = [tuple(row) for _, row in df.iterrows()]

    if _use_pg():
        _import_pg(rows)
        log.info(f"完了: {len(rows)}行処理（重複スキップ）→ Supabase")
    else:
        inserted, skipped = _import_sqlite(rows)
        log.info(f"完了: {inserted}件追加, {skipped}件重複スキップ → SQLite")

    return len(rows)


def _import_sqlite(rows: list) -> tuple[int, int]:
    cfg = _cfg()
    db_path = BASE_DIR / cfg.get("db_path_sqlite", "pos_data.db")
    con = sqlite3.connect(str(db_path))
    con.execute(CREATE_SQLITE)
    con.commit()
    inserted = skipped = 0
    sql = f"INSERT OR IGNORE INTO sales VALUES (NULL, {','.join(['?']*len(COLUMNS))})"
    for row in rows:
        before = con.total_changes
        con.execute(sql, row)
        if con.total_changes > before:
            inserted += 1
        else:
            skipped += 1
    con.commit()
    con.close()
    return inserted, skipped


def _import_pg(rows: list):
    cfg = _cfg()
    sql = (
        f"INSERT INTO sales ({', '.join(COLUMNS)}) "
        f"VALUES ({', '.join(['%s'] * len(COLUMNS))}) "
        "ON CONFLICT (pos_date, store_code, plu_code) DO NOTHING"
    )
    con = psycopg2.connect(cfg["db_url"])
    cur = con.cursor()
    cur.execute(CREATE_PG)
    con.commit()
    psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    con.commit()
    cur.close()
    con.close()


def import_all_downloads():
    cfg = _cfg()
    dl_dir = BASE_DIR / cfg["download_dir"]
    csv_files = sorted(dl_dir.glob("????????.csv"))  # YYYYMMDD.csv のみ対象
    if not csv_files:
        log.info("取り込むCSVファイルがありません。")
        return
    total = 0
    for f in csv_files:
        total += import_csv(str(f))
    log.info(f"全ファイル取り込み完了: 合計{total}行処理")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        import_csv(sys.argv[1])
    else:
        import_all_downloads()
