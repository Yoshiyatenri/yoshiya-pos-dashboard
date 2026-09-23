"""DB接続ヘルパー（SQLite / Supabase 自動切替）
売上管理/pos_system の import_db.py / dashboard.py と同じ方式を踏襲する。
"""
import json
import os
import sqlite3
from pathlib import Path

try:
    import psycopg2
    _psycopg2_ok = True
except ImportError:
    _psycopg2_ok = False

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"

# 本番（Render）では環境変数から読み込む。ローカルではconfig.jsonを使う
_ENV_KEYS = {
    "db_url": "EMPLOYEE_PORTAL_DB_URL",
    "admin_password": "EMPLOYEE_PORTAL_ADMIN_PASSWORD",
    "general_password": "EMPLOYEE_PORTAL_GENERAL_PASSWORD",
    "secret_key": "EMPLOYEE_PORTAL_SECRET_KEY",
}

_config_override: dict = {}


def set_config_override(overrides: dict) -> None:
    """テスト用に設定値を上書きする"""
    global _config_override
    _config_override = overrides


def load_config() -> dict:
    cfg = {}
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for key, env_name in _ENV_KEYS.items():
        value = os.environ.get(env_name)
        if value:
            cfg[key] = value
    cfg.update(_config_override)
    return cfg


def get_db_url() -> str:
    return load_config().get("db_url", "")


def use_pg() -> bool:
    """Supabaseを使うかどうか（URLが正しく設定されている場合のみ）"""
    url = get_db_url()
    if not url or "XXXXXXXXXX" in url:
        return False
    if not _psycopg2_ok:
        raise RuntimeError("db_url が設定されていますが psycopg2 が読み込めません")
    return True


def get_sqlite_path() -> str:
    return str(BASE_DIR / load_config().get("db_path_sqlite", "employee_portal.db"))


def get_conn():
    """DB接続を返す（SQLite / Supabase 自動切替）"""
    if use_pg():
        return psycopg2.connect(get_db_url())
    return sqlite3.connect(get_sqlite_path())


def ph(n: int) -> str:
    """プレースホルダーをn個生成（SQLite:? / PostgreSQL:%s）"""
    mark = "%s" if use_pg() else "?"
    return ",".join([mark] * n)


def fix(sql: str) -> str:
    """SQLite用にプレースホルダーを変換（%s → ?）"""
    if use_pg():
        return sql
    return sql.replace("%s", "?")


def insert_returning_id(cur, sql: str, params: tuple) -> int:
    """INSERT文を実行し、新規作成したレコードのidを返す（SQLite/Postgres両対応）"""
    if use_pg():
        cur.execute(fix(sql) + " RETURNING id", params)
        return cur.fetchone()[0]
    cur.execute(fix(sql), params)
    return cur.lastrowid


CREATE_SQLITE: dict[str, str] = {
    "employees": """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """,
    "goals": """
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            goal_text TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """,
    "goal_scores": """
        CREATE TABLE IF NOT EXISTS goal_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            comment TEXT,
            scored_at TEXT NOT NULL
        )
    """,
    "surveys": """
        CREATE TABLE IF NOT EXISTS surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            is_anonymous INTEGER NOT NULL DEFAULT 0,
            is_open INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """,
    "survey_questions": """
        CREATE TABLE IF NOT EXISTS survey_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL,
            choices TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """,
    "survey_responses": """
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            employee_id INTEGER,
            submitted_at TEXT NOT NULL
        )
    """,
    "survey_answers": """
        CREATE TABLE IF NOT EXISTS survey_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            answer_text TEXT
        )
    """,
    "proposals": """
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '未対応',
            created_at TEXT NOT NULL
        )
    """,
}


def init_schema(conn=None) -> None:
    """全テーブルを作成する（存在しない場合のみ）"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    cur = conn.cursor()
    for table_sql in CREATE_SQLITE.values():
        sql = table_sql
        if use_pg():
            sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        cur.execute(sql)
    conn.commit()
    cur.close()
    if own_conn:
        conn.close()
