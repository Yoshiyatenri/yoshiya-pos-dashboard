"""
取引レポートCSVをvisitorsテーブルに取り込む

対応ファイル:
  全店: 「全店  取引レポート (レジ別) 【ＣＳＶ】  [2026.09.08 ～ 2026.09.08].csv」
  1店舗: 「店舗：6 取引レポート (レジ別) 【ＣＳＶ】  [2026.09.08 ～ 2026.09.08].csv」

CSVの構造:
  縦: 項目名（客数, 税込合計, ...）
  横: 合計列 + 店舗コード:店舗名[レジ番号]
  → 同じ店舗コードのレジ列を合計して来店客数を算出

実行方法:
  python import_visitors.py          # downloadsフォルダ内を全件処理
  python import_visitors.py 20260908 # 日付指定で対象ファイルを絞り込み
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

# ファイル名から日付を取得（全店・1店舗共通）
DATE_RE = re.compile(r'\[(\d{4})\.(\d{2})\.(\d{2})')
# ファイル名から店舗コードを取得（1店舗ファイル用）
SINGLE_STORE_RE = re.compile(r'店舗：(\d+)')
# ヘッダー列から 店舗コード:店舗名[レジ番号] を解析
HEADER_COL_RE = re.compile(r'^(\d+):(.+?)\[')


def _cfg():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _use_pg() -> bool:
    url = _cfg().get("db_url", "")
    return _psycopg2_ok and bool(url) and "XXXXXXXXXX" not in url


def _read_csv(csv_path: Path) -> tuple[list[str], list[list[str]]] | None:
    """CSVをShift-JISで読み込み、(ヘッダー列リスト, データ行リスト) を返す"""
    try:
        raw = csv_path.read_bytes()
        text = raw.decode("shift_jis", errors="replace")
    except Exception as e:
        log.error(f"ファイル読み込みエラー: {csv_path.name} → {e}")
        return None
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines:
        return None
    header = [c.strip() for c in lines[0].split(",")]
    rows = [[c.strip() for c in line.split(",")] for line in lines[1:] if line.strip()]
    return header, rows


def _find_visitors_row(rows: list[list[str]]) -> list[str] | None:
    """「客数」行を返す"""
    for row in rows:
        if row and row[0] == "客数":
            return row
    return None


def parse_allstores_csv(csv_path: Path) -> list[tuple[str, int, str, int]]:
    """
    全店舗CSVをパースして [(pos_date, store_code, store_name, visitors_count), ...] を返す。
    """
    dm = DATE_RE.search(csv_path.name)
    if not dm:
        log.warning(f"ファイル名から日付を取得できません: {csv_path.name}")
        return []
    pos_date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

    result = _read_csv(csv_path)
    if result is None:
        return []
    header, rows = result

    # ヘッダーから店舗コード → {name, indices} マッピングを構築
    store_map: dict[int, dict] = {}
    for i, col in enumerate(header):
        if i <= 1:  # 「項目名」「合計」はスキップ
            continue
        m = HEADER_COL_RE.match(col)
        if m:
            sc = int(m.group(1))
            sn = m.group(2).strip()
            if sc not in store_map:
                store_map[sc] = {"name": sn, "indices": []}
            store_map[sc]["indices"].append(i)

    visitors_row = _find_visitors_row(rows)
    if visitors_row is None:
        log.warning(f"「客数」行が見つかりません: {csv_path.name}")
        return []

    records = []
    for store_code, info in store_map.items():
        total = 0
        for idx in info["indices"]:
            try:
                total += int(visitors_row[idx]) if idx < len(visitors_row) else 0
            except (ValueError, IndexError):
                pass
        records.append((pos_date, store_code, info["name"], total))
        log.debug(f"  店舗{store_code}({info['name']}) 客数={total}")

    log.info(f"{csv_path.name} → {pos_date} 全{len(records)}店舗パース完了")
    return records


def parse_single_store_csv(csv_path: Path) -> list[tuple[str, int, str, int]]:
    """
    1店舗CSVをパースして [(pos_date, store_code, store_name, visitors_count)] を返す。
    """
    sm = SINGLE_STORE_RE.search(csv_path.name)
    dm = DATE_RE.search(csv_path.name)
    if not sm or not dm:
        log.warning(f"ファイル名から店舗コード・日付を取得できません: {csv_path.name}")
        return []
    store_code = int(sm.group(1))
    pos_date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

    result = _read_csv(csv_path)
    if result is None:
        return []
    header, rows = result

    # ヘッダー3列目から店舗名を取得
    store_name = ""
    if len(header) >= 3:
        hm = HEADER_COL_RE.match(header[2])
        if hm:
            store_name = hm.group(2).strip()

    visitors_row = _find_visitors_row(rows)
    if visitors_row is None:
        log.warning(f"「客数」行が見つかりません: {csv_path.name}")
        return []

    try:
        visitors_count = int(visitors_row[1])  # 「合計」列
    except (ValueError, IndexError):
        log.warning(f"客数の合計値を取得できません: {csv_path.name}")
        return []

    log.info(f"{csv_path.name} → {pos_date} 店舗{store_code}({store_name}) 客数={visitors_count}")
    return [(pos_date, store_code, store_name, visitors_count)]


def import_file(csv_path: Path) -> int:
    """CSVをパースしてvisitorsテーブルに取り込む。追加件数を返す"""
    name = csv_path.name
    if "全店" in name:
        records = parse_allstores_csv(csv_path)
    elif "店舗：" in name:
        records = parse_single_store_csv(csv_path)
    else:
        log.warning(f"対象外のファイル: {name}")
        return 0

    if not records:
        return 0

    if _use_pg():
        return _insert_pg_batch(records)
    else:
        return _insert_sqlite_batch(records)


def _insert_sqlite_batch(records: list[tuple]) -> int:
    cfg = _cfg()
    db_path = BASE_DIR / cfg.get("db_path_sqlite", "pos_data.db")
    con = sqlite3.connect(str(db_path))
    con.execute(CREATE_SQLITE)
    con.commit()
    inserted = 0
    for pos_date, store_code, store_name, visitors_count in records:
        before = con.total_changes
        con.execute(
            "INSERT OR IGNORE INTO visitors (pos_date, store_code, store_name, visitors_count) VALUES (?, ?, ?, ?)",
            (pos_date, store_code, store_name, visitors_count),
        )
        if con.total_changes > before:
            inserted += 1
    con.commit()
    con.close()
    log.info(f"  → {inserted}件追加, {len(records)-inserted}件スキップ（SQLite）")
    return inserted


def _insert_pg_batch(records: list[tuple]) -> int:
    cfg = _cfg()
    con = psycopg2.connect(cfg["db_url"])
    cur = con.cursor()
    cur.execute(CREATE_PG)
    inserted = 0
    for pos_date, store_code, store_name, visitors_count in records:
        cur.execute(
            "INSERT INTO visitors (pos_date, store_code, store_name, visitors_count) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (pos_date, store_code) DO NOTHING",
            (pos_date, store_code, store_name, visitors_count),
        )
        if cur.rowcount > 0:
            inserted += 1
    con.commit()
    cur.close()
    con.close()
    log.info(f"  → {inserted}件追加, {len(records)-inserted}件スキップ（Supabase）")
    return inserted


def run(date_filter: str = "") -> int:
    cfg = _cfg()
    dl_dir = BASE_DIR / cfg.get("download_dir", "downloads")
    paths = list(dl_dir.glob("*取引レポート*.csv"))
    if date_filter:
        # 20260908 → 2026.09.08 形式で絞り込み
        d = f"{date_filter[:4]}.{date_filter[4:6]}.{date_filter[6:]}"
        paths = [p for p in paths if d in p.name]
    if not paths:
        log.info("取引レポートCSVが見つかりませんでした")
        return 0

    total = 0
    for p in sorted(paths):
        total += import_file(p)

    log.info(f"=== 処理完了: 合計{total}件追加 ===")
    return total


if __name__ == "__main__":
    date_filter = sys.argv[1] if len(sys.argv) > 1 else ""
    run(date_filter)
