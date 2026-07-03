"""
SQLiteのデータをSupabaseに一括移行するスクリプト
初回セットアップ時に1度だけ実行する
実行: python migrate_to_supabase.py
"""
import json
import sqlite3
from pathlib import Path

import psycopg2
import psycopg2.extras

BASE_DIR = Path(__file__).parent
cfg = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))

SQLITE_PATH = BASE_DIR / cfg.get("db_path_sqlite", "pos_data.db")
PG_URL = cfg["db_url"]

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    pos_date TEXT,
    store_code INTEGER,
    store_name TEXT,
    mid_cat_code INTEGER,
    mid_cat_name TEXT,
    small_cat_code INTEGER,
    small_cat_name TEXT,
    class_code TEXT,
    class_name TEXT,
    cat_code INTEGER,
    cat_name TEXT,
    liquor_cat_code TEXT,
    liquor_cat_name TEXT,
    plu_code TEXT,
    plu_name TEXT,
    spec TEXT,
    volume TEXT,
    alcohol REAL,
    master_cost REAL,
    master_price REAL,
    sales_amount REAL,
    sales_qty INTEGER,
    sales_customers INTEGER,
    gross_profit REAL,
    markdown_amount REAL,
    markdown_qty INTEGER,
    special_sales_amount REAL,
    special_discount_qty INTEGER,
    special_gross_profit REAL,
    plan_discount_amount REAL,
    last_sale_time TEXT,
    weight REAL,
    return_amount REAL,
    return_qty INTEGER,
    return_bottle_amount REAL,
    return_bottle_qty INTEGER,
    UNIQUE(pos_date, store_code, plu_code)
)
"""

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

INSERT_SQL = (
    f"INSERT INTO sales ({', '.join(COLUMNS)}) "
    f"VALUES ({', '.join(['%s'] * len(COLUMNS))}) "
    "ON CONFLICT (pos_date, store_code, plu_code) DO NOTHING"
)


def migrate():
    if not SQLITE_PATH.exists():
        print(f"SQLiteファイルが見つかりません: {SQLITE_PATH}")
        return

    print(f"SQLite読み込み中: {SQLITE_PATH}")
    sqlite_con = sqlite3.connect(str(SQLITE_PATH))
    rows = sqlite_con.execute(
        f"SELECT {', '.join(COLUMNS)} FROM sales"
    ).fetchall()
    sqlite_con.close()
    print(f"  {len(rows)}件取得")

    print(f"Supabaseに接続中...")
    pg_con = psycopg2.connect(PG_URL)
    cur = pg_con.cursor()
    cur.execute(CREATE_SQL)
    pg_con.commit()

    # Noneに変換（SQLiteのNULLはPythonのNoneになっているので問題なし）
    print(f"  データ転送中（500件ずつ）...")
    psycopg2.extras.execute_batch(cur, INSERT_SQL, rows, page_size=500)
    pg_con.commit()
    cur.close()
    pg_con.close()

    print(f"移行完了: {len(rows)}件処理（重複は自動スキップ）")


if __name__ == "__main__":
    migrate()
