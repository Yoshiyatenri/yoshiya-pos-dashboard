import sqlite3

import db as db_module


def test_init_schema_creates_all_tables(tmp_path):
    db_module.set_config_override({
        "db_url": "",
        "db_path_sqlite": str(tmp_path / "schema_test.db"),
    })
    db_module.init_schema()

    conn = sqlite3.connect(str(tmp_path / "schema_test.db"))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    conn.close()

    expected = {
        "employees", "goals", "goal_scores",
        "surveys", "survey_questions", "survey_responses", "survey_answers",
        "proposals",
    }
    assert expected.issubset(tables)


def test_use_pg_is_false_when_db_url_empty(tmp_path):
    db_module.set_config_override({"db_url": "", "db_path_sqlite": str(tmp_path / "x.db")})
    assert db_module.use_pg() is False


def test_fix_converts_placeholder_for_sqlite(tmp_path):
    db_module.set_config_override({"db_url": "", "db_path_sqlite": str(tmp_path / "x.db")})
    assert db_module.fix("SELECT * FROM t WHERE id = %s") == "SELECT * FROM t WHERE id = ?"


def test_insert_returning_id_returns_new_row_id(tmp_path):
    db_module.set_config_override({"db_url": "", "db_path_sqlite": str(tmp_path / "insert_test.db")})
    db_module.init_schema()
    conn = db_module.get_conn()
    cur = conn.cursor()
    new_id = db_module.insert_returning_id(
        cur,
        "INSERT INTO employees (name, is_active, created_at) VALUES (%s, 1, %s)",
        ("テスト太郎", "2026-09-23T00:00:00"),
    )
    conn.commit()
    cur.execute(db_module.fix("SELECT name FROM employees WHERE id = %s"), (new_id,))
    row = cur.fetchone()
    conn.close()
    assert row[0] == "テスト太郎"
