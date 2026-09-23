# 従業員ポータル（目標自己採点・アンケート・提案） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 天理店の従業員向けに、目標の自己採点・アンケート（匿名/記名）・提案（匿名/記名）を1つのWebポータルとして提供する。

**Architecture:** Flask製の軽量Webアプリ（Blueprintで機能ごとにファイル分割）。DBはSQLite（ローカル開発・テスト）とSupabase(PostgreSQL、本番)を自動切替する、既存POSシステム（`売上管理/pos_system`）と同じ方式を踏襲する。Renderの無料枠にデプロイする。

**Tech Stack:** Python 3.12, Flask, psycopg2-binary（Supabase接続）, openpyxl（アンケート結果のExcel出力）, gunicorn（本番実行）, pytest（テスト）

**参照仕様書:** `docs/superpowers/specs/2026-09-23-employee-portal-design.md`

## Global Constraints

- 対象は天理店のみ（他店舗を意識した拡張は行わない）
- 認証は「共通パスワード（一般）＋名前選択」「管理者パスワード」の2種類のみ（個人ごとのID/PWは作らない）
- 匿名のアンケート回答・提案は、`employee_id`をNULLのまま保存し、IPアドレス等の個人特定情報は一切記録しない
- 目標は店長が従業員ごとに登録する。従業員自身は目標を作成できない
- 自己採点は5段階評価＋コメントとし、日時つきで何度でも記録できる（頻度は固定しない）
- アンケートは店長が質問（自由記述/選択式）を自由に作成できる
- アンケート集計結果はExcel（`.xlsx`）でダウンロードできる（`openpyxl`使用）
- 設定値（パスワード・DB接続情報等）は`config.json`に集約し、Gitには含めない。Render本番環境では環境変数から読み込めるようにする
- コメント・ログ・画面文言はすべて日本語
- 新規フォルダー: `スタッフ管理/employee_portal/`（既存フォルダーは変更しない）

---

## Task 1: プロジェクト雛形・DB接続層

**Files:**
- Create: `スタッフ管理/employee_portal/db.py`
- Create: `スタッフ管理/employee_portal/config.example.json`
- Create: `スタッフ管理/employee_portal/requirements.txt`
- Create: `スタッフ管理/employee_portal/requirements-dev.txt`
- Create: `スタッフ管理/employee_portal/tests/conftest.py`
- Create: `スタッフ管理/employee_portal/tests/test_db.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: なし（最初のタスク）
- Produces:
  - `db.load_config() -> dict`
  - `db.set_config_override(overrides: dict) -> None`（テスト用の設定上書き）
  - `db.get_db_url() -> str`
  - `db.use_pg() -> bool`
  - `db.get_sqlite_path() -> str`
  - `db.get_conn()`（SQLite/Postgres自動切替の接続オブジェクトを返す）
  - `db.ph(n: int) -> str`
  - `db.fix(sql: str) -> str`
  - `db.insert_returning_id(cur, sql: str, params: tuple) -> int`
  - `db.init_schema(conn=None) -> None`
  - `db.CREATE_SQLITE: dict[str, str]`（テーブル名→CREATE TABLE文）

- [ ] **Step 1: 失敗するテストを書く**

`スタッフ管理/employee_portal/tests/conftest.py`:

```python
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
```

`スタッフ管理/employee_portal/tests/test_db.py`:

```python
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
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_db.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'db'`）

- [ ] **Step 3: `db.py`を実装する**

`スタッフ管理/employee_portal/db.py`:

```python
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
    return _psycopg2_ok and bool(url) and "XXXXXXXXXX" not in url


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
```

`スタッフ管理/employee_portal/config.example.json`:

```json
{
  "db_url": "",
  "db_path_sqlite": "employee_portal.db",
  "general_password": "CHANGE_ME",
  "admin_password": "CHANGE_ME",
  "secret_key": "CHANGE_ME"
}
```

`スタッフ管理/employee_portal/requirements.txt`:

```
flask
psycopg2-binary
openpyxl
gunicorn
```

`スタッフ管理/employee_portal/requirements-dev.txt`:

```
pytest
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `cd "スタッフ管理/employee_portal" && pip install -r requirements.txt -r requirements-dev.txt && python -m pytest tests/test_db.py -v`
Expected: PASS（4件成功）

- [ ] **Step 5: `.gitignore`に設定ファイル・ローカルDBを追記する**

`.gitignore`の「認証情報を含む設定ファイル」セクションに追記:

```
売上管理/seisan_config.json
SNS/config.json
スタッフ管理/employee_portal/config.json
スタッフ管理/employee_portal/employee_portal.db
```

- [ ] **Step 6: コミット**

```bash
git add "スタッフ管理/employee_portal/db.py" "スタッフ管理/employee_portal/config.example.json" "スタッフ管理/employee_portal/requirements.txt" "スタッフ管理/employee_portal/requirements-dev.txt" "スタッフ管理/employee_portal/tests/conftest.py" "スタッフ管理/employee_portal/tests/test_db.py" .gitignore
git commit -m "feat(employee_portal): DB接続層（SQLite/Supabase自動切替）を追加"
```

---

## Task 2: 認証（ログイン・名前選択・ロール制御）

**Files:**
- Create: `スタッフ管理/employee_portal/auth.py`
- Create: `スタッフ管理/employee_portal/app.py`
- Create: `スタッフ管理/employee_portal/templates/base.html`
- Create: `スタッフ管理/employee_portal/templates/login.html`
- Create: `スタッフ管理/employee_portal/templates/select_employee.html`
- Create: `スタッフ管理/employee_portal/templates/admin_menu.html`
- Create: `スタッフ管理/employee_portal/templates/employee_menu.html`
- Create: `スタッフ管理/employee_portal/templates/error.html`
- Create: `スタッフ管理/employee_portal/static/style.css`
- Modify: `スタッフ管理/employee_portal/tests/conftest.py`
- Create: `スタッフ管理/employee_portal/tests/test_auth.py`

**Interfaces:**
- Consumes: `db.get_conn`, `db.fix`, `db.load_config`, `db.set_config_override`, `db.init_schema`（Task 1）
- Produces:
  - Blueprint `auth.bp`（`auth.login`, `auth.select_employee`, `auth.logout`）
  - `auth.login_required(view)` / `auth.admin_required(view)` / `auth.employee_required(view)` デコレータ
  - `app.create_app() -> Flask`（エンドポイント `index`, `admin_menu`, `employee_menu`）
  - `tests/conftest.py`の`app`・`client`フィクスチャ（以降の全タスクで再利用）

- [ ] **Step 1: 失敗するテストを書く**

`スタッフ管理/employee_portal/tests/conftest.py`（全文を置き換え）:

```python
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db as db_module  # noqa: E402
from app import create_app  # noqa: E402


@pytest.fixture
def app(tmp_path):
    db_module.set_config_override({
        "db_url": "",
        "db_path_sqlite": str(tmp_path / "test.db"),
        "admin_password": "admin123",
        "general_password": "general123",
        "secret_key": "test-secret",
    })
    application = create_app()
    application.testing = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()
```

`スタッフ管理/employee_portal/tests/test_auth.py`:

```python
def test_login_page_loads(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_login_with_admin_password_redirects_to_admin_menu(client):
    resp = client.post("/login", data={"password": "admin123"}, follow_redirects=True)
    assert "店長メニュー".encode("utf-8") in resp.data


def test_login_with_general_password_redirects_to_select_employee(client):
    resp = client.post("/login", data={"password": "general123"}, follow_redirects=True)
    assert "お名前を選択してください".encode("utf-8") in resp.data


def test_login_with_wrong_password_shows_error(client):
    resp = client.post("/login", data={"password": "wrong"}, follow_redirects=True)
    assert "パスワードが違います".encode("utf-8") in resp.data


def test_admin_menu_requires_login(client):
    resp = client.get("/admin", follow_redirects=True)
    assert "パスワードを入力".encode("utf-8") in resp.data or "ログイン".encode("utf-8") in resp.data


def test_employee_menu_requires_employee_selected(client):
    client.post("/login", data={"password": "general123"})
    resp = client.get("/employee", follow_redirects=True)
    assert "お名前を選択してください".encode("utf-8") in resp.data
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_auth.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app'`）

- [ ] **Step 3: `auth.py` / `app.py` / テンプレートを実装する**

`スタッフ管理/employee_portal/auth.py`:

```python
"""ログイン・ロール判定（共通パスワード＋名前選択 / 管理者パスワード）"""
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import fix, get_conn, load_config

bp = Blueprint("auth", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "role" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def employee_required(view):
    """従業員ロールかつ名前選択済みであることを要求する"""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "employee":
            return redirect(url_for("auth.login"))
        if not session.get("employee_id"):
            return redirect(url_for("auth.select_employee"))
        return view(*args, **kwargs)
    return wrapped


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        cfg = load_config()
        if pw and pw == cfg.get("admin_password"):
            session.clear()
            session["role"] = "admin"
            return redirect(url_for("admin_menu"))
        if pw and pw == cfg.get("general_password"):
            session.clear()
            session["role"] = "employee"
            return redirect(url_for("auth.select_employee"))
        flash("パスワードが違います")
    return render_template("login.html")


@bp.route("/select-employee", methods=["GET", "POST"])
def select_employee():
    if session.get("role") != "employee":
        return redirect(url_for("auth.login"))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM employees WHERE is_active = 1 ORDER BY name")
    employees = cur.fetchall()
    cur.close()
    conn.close()

    if request.method == "POST":
        employee_id = request.form.get("employee_id", "")
        match = next((e for e in employees if str(e[0]) == employee_id), None)
        if match:
            session["employee_id"] = match[0]
            session["employee_name"] = match[1]
            return redirect(url_for("employee_menu"))
        flash("名前を選択してください")

    return render_template("select_employee.html", employees=employees)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
```

`スタッフ管理/employee_portal/app.py`:

```python
"""従業員ポータル Flask アプリケーション エントリポイント"""
import logging
import os

from flask import Flask, redirect, render_template, session, url_for

import auth
from db import init_schema, load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    cfg = load_config()
    app.secret_key = cfg.get("secret_key", "dev-secret-change-me")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    init_schema()

    app.register_blueprint(auth.bp)

    @app.errorhandler(500)
    def handle_server_error(e):
        log.exception("予期しないエラーが発生しました")
        return render_template("error.html"), 500

    @app.route("/")
    def index():
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_menu"))
        if role == "employee":
            if session.get("employee_id"):
                return redirect(url_for("employee_menu"))
            return redirect(url_for("auth.select_employee"))
        return redirect(url_for("auth.login"))

    @app.route("/admin")
    @auth.admin_required
    def admin_menu():
        return render_template("admin_menu.html")

    @app.route("/employee")
    @auth.employee_required
    def employee_menu():
        return render_template("employee_menu.html", name=session.get("employee_name"))

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    create_app().run(host="0.0.0.0", port=port, debug=False)
```

`スタッフ管理/employee_portal/templates/error.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>エラーが発生しました</h2>
<p>通信エラーが発生しました。時間をおいて再度お試しください。</p>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}よしや天理店 従業員ポータル{% endblock %}</title>
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
<header>
  <h1>よしや天理店 従業員ポータル</h1>
  {% if session.get('role') %}
    <a href="{{ url_for('auth.logout') }}">ログアウト</a>
  {% endif %}
</header>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul class="flash">
    {% for message in messages %}
      <li>{{ message }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
<main>
{% block content %}{% endblock %}
</main>
</body>
</html>
```

`スタッフ管理/employee_portal/templates/login.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>ログイン</h2>
<form method="post">
  <label>パスワードを入力
    <input type="password" name="password" required>
  </label>
  <button type="submit">ログイン</button>
</form>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/select_employee.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>お名前を選択してください</h2>
<form method="post">
  <select name="employee_id" required>
    <option value="">選択してください</option>
    {% for id, name in employees %}
    <option value="{{ id }}">{{ name }}</option>
    {% endfor %}
  </select>
  <button type="submit">決定</button>
</form>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/admin_menu.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>店長メニュー</h2>
<ul>
</ul>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/employee_menu.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ name }} さん、こんにちは</h2>
<ul>
</ul>
{% endblock %}
```

`スタッフ管理/employee_portal/static/style.css`:

```css
body { font-family: sans-serif; margin: 0; padding: 1rem; }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
table { border-collapse: collapse; width: 100%; margin-bottom: 1rem; }
th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }
.flash { background: #fffae6; padding: 0.5rem; list-style: none; }
input, select, textarea, button { font-size: 1rem; padding: 0.4rem; margin: 0.2rem 0; }
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_auth.py -v`
Expected: PASS（6件成功）

- [ ] **Step 5: コミット**

```bash
git add "スタッフ管理/employee_portal/auth.py" "スタッフ管理/employee_portal/app.py" "スタッフ管理/employee_portal/templates" "スタッフ管理/employee_portal/static" "スタッフ管理/employee_portal/tests/conftest.py" "スタッフ管理/employee_portal/tests/test_auth.py"
git commit -m "feat(employee_portal): ログイン・名前選択・ロール制御を追加"
```

---

## Task 3: 従業員マスタ管理

**Files:**
- Create: `スタッフ管理/employee_portal/employees.py`
- Modify: `スタッフ管理/employee_portal/app.py`
- Modify: `スタッフ管理/employee_portal/templates/admin_menu.html`
- Create: `スタッフ管理/employee_portal/templates/employees_admin.html`
- Create: `スタッフ管理/employee_portal/tests/test_employees.py`

**Interfaces:**
- Consumes: `auth.admin_required`（Task 2）, `db.get_conn`, `db.fix`（Task 1）
- Produces: Blueprint `employees.bp`（`employees.list_employees`, `employees.add_employee`, `employees.deactivate_employee`, `employees.activate_employee`）

- [ ] **Step 1: 失敗するテストを書く**

`スタッフ管理/employee_portal/tests/test_employees.py`:

```python
def _login_admin(client):
    client.post("/login", data={"password": "admin123"})


def test_add_employee_appears_in_list(client):
    _login_admin(client)
    client.post("/admin/employees/add", data={"name": "山田花子"}, follow_redirects=True)
    resp = client.get("/admin/employees/")
    assert "山田花子".encode("utf-8") in resp.data


def test_add_employee_without_name_shows_error(client):
    _login_admin(client)
    resp = client.post("/admin/employees/add", data={"name": ""}, follow_redirects=True)
    assert "名前を入力してください".encode("utf-8") in resp.data


def test_deactivate_employee_hides_from_active_list(client):
    _login_admin(client)
    client.post("/admin/employees/add", data={"name": "退職予定者"})

    import db as db_module
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM employees WHERE name = %s"), ("退職予定者",))
    employee_id = cur.fetchone()[0]
    conn.close()

    client.post(f"/admin/employees/{employee_id}/deactivate", follow_redirects=True)
    resp = client.get("/admin/employees/")
    assert "退職".encode("utf-8") in resp.data


def test_employees_page_requires_admin(client):
    resp = client.get("/admin/employees/", follow_redirects=True)
    assert "パスワードを入力".encode("utf-8") in resp.data
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_employees.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'employees'`、または404）

- [ ] **Step 3: `employees.py`を実装し、`app.py`・`admin_menu.html`を更新する**

`スタッフ管理/employee_portal/employees.py`:

```python
"""従業員マスタ管理（店長のみ）"""
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from auth import admin_required
from db import fix, get_conn

bp = Blueprint("employees", __name__, url_prefix="/admin/employees")


@bp.route("/")
@admin_required
def list_employees():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, is_active FROM employees ORDER BY name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("employees_admin.html", employees=rows)


@bp.route("/add", methods=["POST"])
@admin_required
def add_employee():
    name = request.form.get("name", "").strip()
    if not name:
        flash("名前を入力してください")
        return redirect(url_for("employees.list_employees"))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        fix("INSERT INTO employees (name, is_active, created_at) VALUES (%s, 1, %s)"),
        (name, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    cur.close()
    conn.close()
    flash(f"{name} さんを登録しました")
    return redirect(url_for("employees.list_employees"))


@bp.route("/<int:employee_id>/deactivate", methods=["POST"])
@admin_required
def deactivate_employee(employee_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("UPDATE employees SET is_active = 0 WHERE id = %s"), (employee_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("employees.list_employees"))


@bp.route("/<int:employee_id>/activate", methods=["POST"])
@admin_required
def activate_employee(employee_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("UPDATE employees SET is_active = 1 WHERE id = %s"), (employee_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("employees.list_employees"))
```

`スタッフ管理/employee_portal/app.py`（`import auth`の下に追記し、blueprint登録を追加）:

```python
"""従業員ポータル Flask アプリケーション エントリポイント"""
import logging
import os

from flask import Flask, redirect, render_template, session, url_for

import auth
import employees
from db import init_schema, load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    cfg = load_config()
    app.secret_key = cfg.get("secret_key", "dev-secret-change-me")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    init_schema()

    app.register_blueprint(auth.bp)
    app.register_blueprint(employees.bp)

    @app.errorhandler(500)
    def handle_server_error(e):
        log.exception("予期しないエラーが発生しました")
        return render_template("error.html"), 500

    @app.route("/")
    def index():
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_menu"))
        if role == "employee":
            if session.get("employee_id"):
                return redirect(url_for("employee_menu"))
            return redirect(url_for("auth.select_employee"))
        return redirect(url_for("auth.login"))

    @app.route("/admin")
    @auth.admin_required
    def admin_menu():
        return render_template("admin_menu.html")

    @app.route("/employee")
    @auth.employee_required
    def employee_menu():
        return render_template("employee_menu.html", name=session.get("employee_name"))

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    create_app().run(host="0.0.0.0", port=port, debug=False)
```

`スタッフ管理/employee_portal/templates/admin_menu.html`（全文差し替え）:

```html
{% extends "base.html" %}
{% block content %}
<h2>店長メニュー</h2>
<ul>
  <li><a href="{{ url_for('employees.list_employees') }}">従業員マスタ管理</a></li>
</ul>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/employees_admin.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>従業員マスタ管理</h2>
<form method="post" action="{{ url_for('employees.add_employee') }}">
  <input type="text" name="name" placeholder="従業員名" required>
  <button type="submit">追加</button>
</form>
<table>
  <tr><th>名前</th><th>状態</th><th>操作</th></tr>
  {% for id, name, is_active in employees %}
  <tr>
    <td>{{ name }}</td>
    <td>{{ "在籍" if is_active else "退職" }}</td>
    <td>
      {% if is_active %}
      <form method="post" action="{{ url_for('employees.deactivate_employee', employee_id=id) }}" style="display:inline">
        <button type="submit">退職にする</button>
      </form>
      {% else %}
      <form method="post" action="{{ url_for('employees.activate_employee', employee_id=id) }}" style="display:inline">
        <button type="submit">在籍に戻す</button>
      </form>
      {% endif %}
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_employees.py -v`
Expected: PASS（4件成功）

- [ ] **Step 5: コミット**

```bash
git add "スタッフ管理/employee_portal/employees.py" "スタッフ管理/employee_portal/app.py" "スタッフ管理/employee_portal/templates/admin_menu.html" "スタッフ管理/employee_portal/templates/employees_admin.html" "スタッフ管理/employee_portal/tests/test_employees.py"
git commit -m "feat(employee_portal): 従業員マスタ管理を追加"
```

---

## Task 4: 目標管理・自己採点

**Files:**
- Create: `スタッフ管理/employee_portal/goals.py`
- Modify: `スタッフ管理/employee_portal/app.py`
- Modify: `スタッフ管理/employee_portal/templates/admin_menu.html`
- Modify: `スタッフ管理/employee_portal/templates/employee_menu.html`
- Create: `スタッフ管理/employee_portal/templates/goals_admin.html`
- Create: `スタッフ管理/employee_portal/templates/goal_scores_admin.html`
- Create: `スタッフ管理/employee_portal/templates/goals_employee.html`
- Create: `スタッフ管理/employee_portal/tests/test_goals.py`

**Interfaces:**
- Consumes: `auth.admin_required` / `auth.employee_required`（Task 2）, `db.get_conn` / `db.fix`（Task 1）, `employees`テーブル（Task 3）
- Produces: Blueprint `goals.bp`（`goals.admin_goals`, `goals.add_goal`, `goals.deactivate_goal`, `goals.admin_goal_scores`, `goals.my_goals`, `goals.submit_score`）

- [ ] **Step 1: 失敗するテストを書く**

`スタッフ管理/employee_portal/tests/test_goals.py`:

```python
import db as db_module


def _login_admin(client):
    client.post("/login", data={"password": "admin123"})


def _add_employee_and_login(client, name="採点太郎"):
    _login_admin(client)
    client.post("/admin/employees/add", data={"name": name})
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM employees WHERE name = %s"), (name,))
    employee_id = cur.fetchone()[0]
    conn.close()

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})
    return employee_id


def test_admin_can_add_goal_for_employee(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    resp = client.post(
        "/admin/goals/add",
        data={"employee_id": str(employee_id), "goal_text": "接客満足度を上げる"},
        follow_redirects=True,
    )
    assert "接客満足度を上げる".encode("utf-8") in resp.data


def test_employee_sees_own_goal_and_can_score_it(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "品出しを早くする"})

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    resp = client.get("/goals")
    assert "品出しを早くする".encode("utf-8") in resp.data

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM goals WHERE employee_id = %s"), (employee_id,))
    goal_id = cur.fetchone()[0]
    conn.close()

    resp = client.post(
        f"/goals/{goal_id}/score",
        data={"score": "4", "comment": "だいぶ早くなった"},
        follow_redirects=True,
    )
    assert "採点を記録しました".encode("utf-8") in resp.data


def test_employee_cannot_score_other_employees_goal(client):
    employee_a = _add_employee_and_login(client, name="Aさん")
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_a), "goal_text": "Aさんの目標"})
    client.post("/admin/employees/add", data={"name": "Bさん"})

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM employees WHERE name = %s"), ("Bさん",))
    employee_b = cur.fetchone()[0]
    cur.execute(db_module.fix("SELECT id FROM goals WHERE employee_id = %s"), (employee_a,))
    goal_id = cur.fetchone()[0]
    conn.close()

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_b)})

    resp = client.post(
        f"/goals/{goal_id}/score",
        data={"score": "5", "comment": "なりすまし"},
        follow_redirects=True,
    )
    assert "不正な操作です".encode("utf-8") in resp.data

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT COUNT(*) FROM goal_scores WHERE goal_id = %s"), (goal_id,))
    count = cur.fetchone()[0]
    conn.close()
    assert count == 0
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_goals.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'goals'`、または404）

- [ ] **Step 3: `goals.py`を実装し、`app.py`・メニュー画面を更新する**

`スタッフ管理/employee_portal/goals.py`:

```python
"""目標管理（店長）・自己採点（従業員）"""
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth import admin_required, employee_required
from db import fix, get_conn

bp = Blueprint("goals", __name__)

VALID_SCORES = {"1", "2", "3", "4", "5"}


@bp.route("/admin/goals")
@admin_required
def admin_goals():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM employees WHERE is_active = 1 ORDER BY name")
    employees = cur.fetchall()
    cur.execute(
        """
        SELECT goals.id, goals.employee_id, employees.name, goals.goal_text, goals.is_active
        FROM goals
        JOIN employees ON employees.id = goals.employee_id
        ORDER BY employees.name, goals.created_at
        """
    )
    goal_rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("goals_admin.html", employees=employees, goals=goal_rows)


@bp.route("/admin/goals/add", methods=["POST"])
@admin_required
def add_goal():
    employee_id = request.form.get("employee_id", "")
    goal_text = request.form.get("goal_text", "").strip()
    if not employee_id or not goal_text:
        flash("従業員と目標内容を入力してください")
        return redirect(url_for("goals.admin_goals"))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        fix("INSERT INTO goals (employee_id, goal_text, is_active, created_at) VALUES (%s, %s, 1, %s)"),
        (employee_id, goal_text, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    cur.close()
    conn.close()
    flash("目標を登録しました")
    return redirect(url_for("goals.admin_goals"))


@bp.route("/admin/goals/<int:goal_id>/deactivate", methods=["POST"])
@admin_required
def deactivate_goal(goal_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("UPDATE goals SET is_active = 0 WHERE id = %s"), (goal_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("goals.admin_goals"))


@bp.route("/admin/goals/<int:employee_id>/scores")
@admin_required
def admin_goal_scores(employee_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("SELECT id, goal_text FROM goals WHERE employee_id = %s ORDER BY created_at"), (employee_id,))
    goals_list = cur.fetchall()
    scores_by_goal = {}
    for goal_id, _ in goals_list:
        cur.execute(
            fix("SELECT score, comment, scored_at FROM goal_scores WHERE goal_id = %s ORDER BY scored_at"),
            (goal_id,),
        )
        scores_by_goal[goal_id] = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("goal_scores_admin.html", goals=goals_list, scores_by_goal=scores_by_goal)


@bp.route("/goals")
@employee_required
def my_goals():
    employee_id = session["employee_id"]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        fix("SELECT id, goal_text FROM goals WHERE employee_id = %s AND is_active = 1 ORDER BY created_at"),
        (employee_id,),
    )
    goals_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("goals_employee.html", goals=goals_list)


@bp.route("/goals/<int:goal_id>/score", methods=["POST"])
@employee_required
def submit_score(goal_id: int):
    score = request.form.get("score", "")
    comment = request.form.get("comment", "").strip()
    if score not in VALID_SCORES:
        flash("評価は1〜5で選んでください")
        return redirect(url_for("goals.my_goals"))

    employee_id = session["employee_id"]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("SELECT employee_id FROM goals WHERE id = %s"), (goal_id,))
    row = cur.fetchone()
    if not row or row[0] != employee_id:
        cur.close()
        conn.close()
        flash("不正な操作です")
        return redirect(url_for("goals.my_goals"))

    cur.execute(
        fix("INSERT INTO goal_scores (goal_id, score, comment, scored_at) VALUES (%s, %s, %s, %s)"),
        (goal_id, int(score), comment, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    cur.close()
    conn.close()
    flash("採点を記録しました")
    return redirect(url_for("goals.my_goals"))
```

`スタッフ管理/employee_portal/app.py`（`import employees`の下に`import goals`を追記し、blueprint登録を追加）:

```python
"""従業員ポータル Flask アプリケーション エントリポイント"""
import logging
import os

from flask import Flask, redirect, render_template, session, url_for

import auth
import employees
import goals
from db import init_schema, load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    cfg = load_config()
    app.secret_key = cfg.get("secret_key", "dev-secret-change-me")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    init_schema()

    app.register_blueprint(auth.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(goals.bp)

    @app.errorhandler(500)
    def handle_server_error(e):
        log.exception("予期しないエラーが発生しました")
        return render_template("error.html"), 500

    @app.route("/")
    def index():
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_menu"))
        if role == "employee":
            if session.get("employee_id"):
                return redirect(url_for("employee_menu"))
            return redirect(url_for("auth.select_employee"))
        return redirect(url_for("auth.login"))

    @app.route("/admin")
    @auth.admin_required
    def admin_menu():
        return render_template("admin_menu.html")

    @app.route("/employee")
    @auth.employee_required
    def employee_menu():
        return render_template("employee_menu.html", name=session.get("employee_name"))

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    create_app().run(host="0.0.0.0", port=port, debug=False)
```

`スタッフ管理/employee_portal/templates/admin_menu.html`（全文差し替え）:

```html
{% extends "base.html" %}
{% block content %}
<h2>店長メニュー</h2>
<ul>
  <li><a href="{{ url_for('employees.list_employees') }}">従業員マスタ管理</a></li>
  <li><a href="{{ url_for('goals.admin_goals') }}">目標・自己採点</a></li>
</ul>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/employee_menu.html`（全文差し替え）:

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ name }} さん、こんにちは</h2>
<ul>
  <li><a href="{{ url_for('goals.my_goals') }}">目標の自己採点</a></li>
</ul>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/goals_admin.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>目標管理</h2>
<form method="post" action="{{ url_for('goals.add_goal') }}">
  <select name="employee_id" required>
    <option value="">従業員を選択</option>
    {% for id, name in employees %}
    <option value="{{ id }}">{{ name }}</option>
    {% endfor %}
  </select>
  <input type="text" name="goal_text" placeholder="目標内容" required>
  <button type="submit">登録</button>
</form>
<table>
  <tr><th>従業員</th><th>目標</th><th>状態</th><th>操作</th></tr>
  {% for id, employee_id, name, goal_text, is_active in goals %}
  <tr>
    <td>{{ name }}</td>
    <td>{{ goal_text }}</td>
    <td>{{ "有効" if is_active else "終了" }}</td>
    <td>
      <a href="{{ url_for('goals.admin_goal_scores', employee_id=employee_id) }}">採点履歴</a>
      {% if is_active %}
      <form method="post" action="{{ url_for('goals.deactivate_goal', goal_id=id) }}" style="display:inline">
        <button type="submit">終了する</button>
      </form>
      {% endif %}
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/goal_scores_admin.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>採点履歴</h2>
{% for goal_id, goal_text in goals %}
<h3>{{ goal_text }}</h3>
<table>
  <tr><th>日時</th><th>評価</th><th>コメント</th></tr>
  {% for score, comment, scored_at in scores_by_goal[goal_id] %}
  <tr><td>{{ scored_at }}</td><td>{{ score }}</td><td>{{ comment }}</td></tr>
  {% endfor %}
</table>
{% endfor %}
{% endblock %}
```

`スタッフ管理/employee_portal/templates/goals_employee.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>目標の自己採点</h2>
{% for id, goal_text in goals %}
<div class="goal">
  <h3>{{ goal_text }}</h3>
  <form method="post" action="{{ url_for('goals.submit_score', goal_id=id) }}">
    <select name="score" required>
      <option value="">評価を選択</option>
      <option value="1">1</option>
      <option value="2">2</option>
      <option value="3">3</option>
      <option value="4">4</option>
      <option value="5">5</option>
    </select>
    <input type="text" name="comment" placeholder="コメント（任意）">
    <button type="submit">記録する</button>
  </form>
</div>
{% else %}
<p>登録されている目標はまだありません。</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_goals.py -v`
Expected: PASS（3件成功）

- [ ] **Step 5: コミット**

```bash
git add "スタッフ管理/employee_portal/goals.py" "スタッフ管理/employee_portal/app.py" "スタッフ管理/employee_portal/templates/admin_menu.html" "スタッフ管理/employee_portal/templates/employee_menu.html" "スタッフ管理/employee_portal/templates/goals_admin.html" "スタッフ管理/employee_portal/templates/goal_scores_admin.html" "スタッフ管理/employee_portal/templates/goals_employee.html" "スタッフ管理/employee_portal/tests/test_goals.py"
git commit -m "feat(employee_portal): 目標管理・自己採点を追加"
```

---

## Task 5: アンケート作成・回答

**Files:**
- Create: `スタッフ管理/employee_portal/surveys.py`
- Modify: `スタッフ管理/employee_portal/app.py`
- Modify: `スタッフ管理/employee_portal/templates/admin_menu.html`
- Modify: `スタッフ管理/employee_portal/templates/employee_menu.html`
- Create: `スタッフ管理/employee_portal/templates/surveys_admin.html`
- Create: `スタッフ管理/employee_portal/templates/surveys_edit.html`
- Create: `スタッフ管理/employee_portal/templates/surveys_list.html`
- Create: `スタッフ管理/employee_portal/templates/surveys_answer.html`
- Create: `スタッフ管理/employee_portal/tests/test_surveys.py`

**Interfaces:**
- Consumes: `auth.admin_required` / `auth.employee_required`（Task 2）, `db.get_conn` / `db.fix` / `db.insert_returning_id`（Task 1）
- Produces: Blueprint `surveys.bp`（`surveys.admin_surveys`, `surveys.create_survey`, `surveys.edit_survey`, `surveys.add_question`, `surveys.publish_survey`, `surveys.close_survey`, `surveys.list_surveys`, `surveys.answer_survey`）。Jinja フィルター `from_json`（Task 6で結果表示にも使用）

- [ ] **Step 1: 失敗するテストを書く**

`スタッフ管理/employee_portal/tests/test_surveys.py`:

```python
import json

import db as db_module


def _login_admin(client):
    client.post("/login", data={"password": "admin123"})


def _create_survey(client, title="満足度調査", anonymous=False):
    _login_admin(client)
    data = {"title": title}
    if anonymous:
        data["is_anonymous"] = "on"
    client.post("/admin/surveys/create", data=data)
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM surveys WHERE title = %s"), (title,))
    survey_id = cur.fetchone()[0]
    conn.close()
    return survey_id


def _add_employee_and_login(client, name="回答太郎"):
    client.post("/admin/employees/add", data={"name": name})
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM employees WHERE name = %s"), (name,))
    employee_id = cur.fetchone()[0]
    conn.close()

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})
    return employee_id


def test_create_survey_and_add_free_question(client):
    survey_id = _create_survey(client)
    client.post(
        f"/admin/surveys/{survey_id}/questions/add",
        data={"question_text": "職場の良い点は？", "question_type": "free"},
        follow_redirects=True,
    )
    resp = client.get(f"/admin/surveys/{survey_id}/edit")
    assert "職場の良い点は？".encode("utf-8") in resp.data


def test_add_choice_question_requires_choices(client):
    survey_id = _create_survey(client)
    resp = client.post(
        f"/admin/surveys/{survey_id}/questions/add",
        data={"question_text": "満足度は？", "question_type": "choice", "choices": ""},
        follow_redirects=True,
    )
    assert "選択肢を1つ以上入力してください".encode("utf-8") in resp.data


def test_unpublished_survey_not_visible_to_employees(client):
    survey_id = _create_survey(client)
    _add_employee_and_login(client)
    resp = client.get("/surveys")
    assert "満足度調査".encode("utf-8") not in resp.data


def test_published_survey_can_be_answered_by_employee(client):
    survey_id = _create_survey(client)
    client.post(
        f"/admin/surveys/{survey_id}/questions/add",
        data={"question_text": "感想", "question_type": "free"},
    )
    client.post(f"/admin/surveys/{survey_id}/publish")

    employee_id = _add_employee_and_login(client)
    resp = client.get("/surveys")
    assert "満足度調査".encode("utf-8") in resp.data

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM survey_questions WHERE survey_id = %s"), (survey_id,))
    question_id = cur.fetchone()[0]
    conn.close()

    client.post(
        f"/surveys/{survey_id}/answer",
        data={f"question_{question_id}": "良かったです"},
        follow_redirects=True,
    )

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT employee_id FROM survey_responses WHERE survey_id = %s"), (survey_id,))
    row = cur.fetchone()
    conn.close()
    assert row[0] == employee_id


def test_anonymous_survey_does_not_store_employee_id(client):
    survey_id = _create_survey(client, title="匿名調査", anonymous=True)
    client.post(
        f"/admin/surveys/{survey_id}/questions/add",
        data={"question_text": "率直な意見", "question_type": "free"},
    )
    client.post(f"/admin/surveys/{survey_id}/publish")

    _add_employee_and_login(client)
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM survey_questions WHERE survey_id = %s"), (survey_id,))
    question_id = cur.fetchone()[0]
    conn.close()

    client.post(
        f"/surveys/{survey_id}/answer",
        data={f"question_{question_id}": "本音です"},
        follow_redirects=True,
    )

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT employee_id FROM survey_responses WHERE survey_id = %s"), (survey_id,))
    row = cur.fetchone()
    conn.close()
    assert row[0] is None
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_surveys.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'surveys'`、または404）

- [ ] **Step 3: `surveys.py`を実装し、`app.py`・メニュー画面を更新する**

`スタッフ管理/employee_portal/surveys.py`:

```python
"""アンケート作成（店長）・回答（従業員）"""
import json
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth import admin_required, employee_required
from db import fix, get_conn, insert_returning_id

bp = Blueprint("surveys", __name__)


@bp.route("/admin/surveys")
@admin_required
def admin_surveys():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title, is_anonymous, is_open, created_at FROM surveys ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("surveys_admin.html", surveys=rows)


@bp.route("/admin/surveys/create", methods=["POST"])
@admin_required
def create_survey():
    title = request.form.get("title", "").strip()
    is_anonymous = 1 if request.form.get("is_anonymous") == "on" else 0
    if not title:
        flash("タイトルを入力してください")
        return redirect(url_for("surveys.admin_surveys"))

    conn = get_conn()
    cur = conn.cursor()
    survey_id = insert_returning_id(
        cur,
        "INSERT INTO surveys (title, is_anonymous, is_open, created_at) VALUES (%s, %s, 0, %s)",
        (title, is_anonymous, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("surveys.edit_survey", survey_id=survey_id))


@bp.route("/admin/surveys/<int:survey_id>/edit")
@admin_required
def edit_survey(survey_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("SELECT id, title, is_anonymous, is_open FROM surveys WHERE id = %s"), (survey_id,))
    survey = cur.fetchone()
    cur.execute(
        fix(
            "SELECT id, question_text, question_type, choices FROM survey_questions "
            "WHERE survey_id = %s ORDER BY sort_order"
        ),
        (survey_id,),
    )
    questions = cur.fetchall()
    cur.close()
    conn.close()
    if not survey:
        flash("アンケートが見つかりません")
        return redirect(url_for("surveys.admin_surveys"))
    return render_template("surveys_edit.html", survey=survey, questions=questions)


@bp.route("/admin/surveys/<int:survey_id>/questions/add", methods=["POST"])
@admin_required
def add_question(survey_id: int):
    question_text = request.form.get("question_text", "").strip()
    question_type = request.form.get("question_type", "free")
    choices_raw = request.form.get("choices", "").strip()

    if not question_text:
        flash("質問文を入力してください")
        return redirect(url_for("surveys.edit_survey", survey_id=survey_id))

    choices_json = None
    if question_type == "choice":
        choices = [c.strip() for c in choices_raw.split(",") if c.strip()]
        if not choices:
            flash("選択式には選択肢を1つ以上入力してください")
            return redirect(url_for("surveys.edit_survey", survey_id=survey_id))
        choices_json = json.dumps(choices, ensure_ascii=False)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("SELECT COALESCE(MAX(sort_order), -1) FROM survey_questions WHERE survey_id = %s"), (survey_id,))
    next_order = cur.fetchone()[0] + 1
    cur.execute(
        fix(
            "INSERT INTO survey_questions (survey_id, question_text, question_type, choices, sort_order) "
            "VALUES (%s, %s, %s, %s, %s)"
        ),
        (survey_id, question_text, question_type, choices_json, next_order),
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("surveys.edit_survey", survey_id=survey_id))


@bp.route("/admin/surveys/<int:survey_id>/publish", methods=["POST"])
@admin_required
def publish_survey(survey_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("UPDATE surveys SET is_open = 1 WHERE id = %s"), (survey_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("アンケートを公開しました")
    return redirect(url_for("surveys.admin_surveys"))


@bp.route("/admin/surveys/<int:survey_id>/close", methods=["POST"])
@admin_required
def close_survey(survey_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("UPDATE surveys SET is_open = 0 WHERE id = %s"), (survey_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("アンケートを締め切りました")
    return redirect(url_for("surveys.admin_surveys"))


@bp.route("/surveys")
@employee_required
def list_surveys():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM surveys WHERE is_open = 1 ORDER BY created_at DESC")
    open_surveys = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("surveys_list.html", surveys=open_surveys)


@bp.route("/surveys/<int:survey_id>/answer", methods=["GET", "POST"])
@employee_required
def answer_survey(survey_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("SELECT id, title, is_anonymous, is_open FROM surveys WHERE id = %s"), (survey_id,))
    survey = cur.fetchone()
    if not survey or survey[3] != 1:
        cur.close()
        conn.close()
        flash("回答できないアンケートです")
        return redirect(url_for("surveys.list_surveys"))

    cur.execute(
        fix(
            "SELECT id, question_text, question_type, choices FROM survey_questions "
            "WHERE survey_id = %s ORDER BY sort_order"
        ),
        (survey_id,),
    )
    questions = cur.fetchall()

    if request.method == "POST":
        employee_id = None if survey[2] == 1 else session["employee_id"]
        response_id = insert_returning_id(
            cur,
            "INSERT INTO survey_responses (survey_id, employee_id, submitted_at) VALUES (%s, %s, %s)",
            (survey_id, employee_id, datetime.now(timezone.utc).isoformat()),
        )
        for q_id, _, _, _ in questions:
            answer_text = request.form.get(f"question_{q_id}", "").strip()
            cur.execute(
                fix("INSERT INTO survey_answers (response_id, question_id, answer_text) VALUES (%s, %s, %s)"),
                (response_id, q_id, answer_text),
            )
        conn.commit()
        cur.close()
        conn.close()
        flash("回答ありがとうございました")
        return redirect(url_for("surveys.list_surveys"))

    cur.close()
    conn.close()
    return render_template("surveys_answer.html", survey=survey, questions=questions)
```

`スタッフ管理/employee_portal/app.py`（`import goals`の下に`import surveys`を追記し、blueprint登録・Jinjaフィルターを追加）:

```python
"""従業員ポータル Flask アプリケーション エントリポイント"""
import json
import logging
import os

from flask import Flask, redirect, render_template, session, url_for

import auth
import employees
import goals
import surveys
from db import init_schema, load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    cfg = load_config()
    app.secret_key = cfg.get("secret_key", "dev-secret-change-me")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.jinja_env.filters["from_json"] = json.loads

    init_schema()

    app.register_blueprint(auth.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(goals.bp)
    app.register_blueprint(surveys.bp)

    @app.errorhandler(500)
    def handle_server_error(e):
        log.exception("予期しないエラーが発生しました")
        return render_template("error.html"), 500

    @app.route("/")
    def index():
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_menu"))
        if role == "employee":
            if session.get("employee_id"):
                return redirect(url_for("employee_menu"))
            return redirect(url_for("auth.select_employee"))
        return redirect(url_for("auth.login"))

    @app.route("/admin")
    @auth.admin_required
    def admin_menu():
        return render_template("admin_menu.html")

    @app.route("/employee")
    @auth.employee_required
    def employee_menu():
        return render_template("employee_menu.html", name=session.get("employee_name"))

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    create_app().run(host="0.0.0.0", port=port, debug=False)
```

`スタッフ管理/employee_portal/templates/admin_menu.html`（全文差し替え）:

```html
{% extends "base.html" %}
{% block content %}
<h2>店長メニュー</h2>
<ul>
  <li><a href="{{ url_for('employees.list_employees') }}">従業員マスタ管理</a></li>
  <li><a href="{{ url_for('goals.admin_goals') }}">目標・自己採点</a></li>
  <li><a href="{{ url_for('surveys.admin_surveys') }}">アンケート管理</a></li>
</ul>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/employee_menu.html`（全文差し替え）:

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ name }} さん、こんにちは</h2>
<ul>
  <li><a href="{{ url_for('goals.my_goals') }}">目標の自己採点</a></li>
  <li><a href="{{ url_for('surveys.list_surveys') }}">アンケートに回答</a></li>
</ul>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/surveys_admin.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>アンケート管理</h2>
<form method="post" action="{{ url_for('surveys.create_survey') }}">
  <input type="text" name="title" placeholder="タイトル" required>
  <label><input type="checkbox" name="is_anonymous"> 匿名アンケートにする</label>
  <button type="submit">新規作成</button>
</form>
<table>
  <tr><th>タイトル</th><th>匿名</th><th>状態</th><th>操作</th></tr>
  {% for id, title, is_anonymous, is_open, created_at in surveys %}
  <tr>
    <td>{{ title }}</td>
    <td>{{ "匿名" if is_anonymous else "記名" }}</td>
    <td>{{ "公開中" if is_open else "下書き" }}</td>
    <td>
      <a href="{{ url_for('surveys.edit_survey', survey_id=id) }}">編集</a>
      {% if is_open %}
      <form method="post" action="{{ url_for('surveys.close_survey', survey_id=id) }}" style="display:inline">
        <button type="submit">締め切る</button>
      </form>
      {% else %}
      <form method="post" action="{{ url_for('surveys.publish_survey', survey_id=id) }}" style="display:inline">
        <button type="submit">公開する</button>
      </form>
      {% endif %}
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/surveys_edit.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ survey[1] }} の編集</h2>
<h3>質問一覧</h3>
<ul>
  {% for id, text, qtype, choices in questions %}
  <li>{{ text }}（{{ "選択式" if qtype == "choice" else "自由記述" }}）</li>
  {% endfor %}
</ul>
<h3>質問を追加</h3>
<form method="post" action="{{ url_for('surveys.add_question', survey_id=survey[0]) }}">
  <input type="text" name="question_text" placeholder="質問文" required>
  <select name="question_type">
    <option value="free">自由記述</option>
    <option value="choice">選択式</option>
  </select>
  <input type="text" name="choices" placeholder="選択肢（カンマ区切り、選択式のみ）">
  <button type="submit">追加</button>
</form>
{% if not survey[3] %}
<form method="post" action="{{ url_for('surveys.publish_survey', survey_id=survey[0]) }}">
  <button type="submit">このアンケートを公開する</button>
</form>
{% endif %}
{% endblock %}
```

`スタッフ管理/employee_portal/templates/surveys_list.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>アンケート一覧</h2>
<ul>
  {% for id, title in surveys %}
  <li><a href="{{ url_for('surveys.answer_survey', survey_id=id) }}">{{ title }}</a></li>
  {% else %}
  <li>現在回答できるアンケートはありません。</li>
  {% endfor %}
</ul>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/surveys_answer.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ survey[1] }}</h2>
<form method="post">
  {% for id, text, qtype, choices in questions %}
  <div class="question">
    <label>{{ text }}</label>
    {% if qtype == "choice" %}
    <select name="question_{{ id }}" required>
      <option value="">選択してください</option>
      {% for choice in choices|from_json %}
      <option value="{{ choice }}">{{ choice }}</option>
      {% endfor %}
    </select>
    {% else %}
    <textarea name="question_{{ id }}"></textarea>
    {% endif %}
  </div>
  {% endfor %}
  <button type="submit">回答する</button>
</form>
{% endblock %}
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_surveys.py -v`
Expected: PASS（5件成功）

- [ ] **Step 5: コミット**

```bash
git add "スタッフ管理/employee_portal/surveys.py" "スタッフ管理/employee_portal/app.py" "スタッフ管理/employee_portal/templates/admin_menu.html" "スタッフ管理/employee_portal/templates/employee_menu.html" "スタッフ管理/employee_portal/templates/surveys_admin.html" "スタッフ管理/employee_portal/templates/surveys_edit.html" "スタッフ管理/employee_portal/templates/surveys_list.html" "スタッフ管理/employee_portal/templates/surveys_answer.html" "スタッフ管理/employee_portal/tests/test_surveys.py"
git commit -m "feat(employee_portal): アンケート作成・回答を追加"
```

---

## Task 6: アンケート集計・Excel出力

**Files:**
- Modify: `スタッフ管理/employee_portal/surveys.py`
- Modify: `スタッフ管理/employee_portal/templates/surveys_admin.html`
- Create: `スタッフ管理/employee_portal/templates/surveys_results.html`
- Create: `スタッフ管理/employee_portal/tests/test_survey_results.py`

**Interfaces:**
- Consumes: `surveys.py`（Task 5）の`survey_questions` / `survey_answers`テーブル, `openpyxl`
- Produces: `surveys._build_results(survey_id) -> tuple`, エンドポイント`surveys.survey_results`, `surveys.survey_results_excel`

- [ ] **Step 1: 失敗するテストを書く**

`スタッフ管理/employee_portal/tests/test_survey_results.py`:

```python
import db as db_module


def _login_admin(client):
    client.post("/login", data={"password": "admin123"})


def _create_published_survey_with_choice_question(client):
    _login_admin(client)
    client.post("/admin/surveys/create", data={"title": "休憩時間アンケート"})
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM surveys WHERE title = %s"), ("休憩時間アンケート",))
    survey_id = cur.fetchone()[0]
    conn.close()

    client.post(
        f"/admin/surveys/{survey_id}/questions/add",
        data={"question_text": "休憩時間は十分？", "question_type": "choice", "choices": "十分,やや不足,不足"},
    )
    client.post(f"/admin/surveys/{survey_id}/publish")
    return survey_id


def _answer_as_new_employee(client, survey_id, name, answer_map):
    client.post("/admin/employees/add", data={"name": name})
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM employees WHERE name = %s"), (name,))
    employee_id = cur.fetchone()[0]
    conn.close()

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})
    client.post(f"/surveys/{survey_id}/answer", data=answer_map)
    client.get("/logout")
    _login_admin(client)


def test_results_page_shows_choice_counts(client):
    survey_id = _create_published_survey_with_choice_question(client)
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM survey_questions WHERE survey_id = %s"), (survey_id,))
    question_id = cur.fetchone()[0]
    conn.close()

    _answer_as_new_employee(client, survey_id, "回答者A", {f"question_{question_id}": "十分"})
    _answer_as_new_employee(client, survey_id, "回答者B", {f"question_{question_id}": "不足"})

    resp = client.get(f"/admin/surveys/{survey_id}/results")
    assert "回答数: 2".encode("utf-8") in resp.data
    assert "十分".encode("utf-8") in resp.data


def test_results_excel_download_returns_xlsx(client):
    survey_id = _create_published_survey_with_choice_question(client)
    resp = client.get(f"/admin/surveys/{survey_id}/results.xlsx")
    assert resp.status_code == 200
    assert resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_survey_results.py -v`
Expected: FAIL（404、`_build_results`未定義によるエラー）

- [ ] **Step 3: `surveys.py`に集計・Excel出力を追加し、テンプレートを更新する**

`スタッフ管理/employee_portal/surveys.py`の末尾に追記（ファイル冒頭の`import`に`from io import BytesIO`と`from openpyxl import Workbook`、`send_file`を追加すること）:

`スタッフ管理/employee_portal/surveys.py`（先頭のimport部分を差し替え）:

```python
"""アンケート作成（店長）・回答（従業員）・集計・Excel出力"""
import json
from datetime import datetime, timezone
from io import BytesIO

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from openpyxl import Workbook

from auth import admin_required, employee_required
from db import fix, get_conn, insert_returning_id

bp = Blueprint("surveys", __name__)
```

（Task 5で作成した各関数はそのまま残し）ファイル末尾に以下を追加する:

```python
def _build_results(survey_id: int):
    """アンケートの集計結果を組み立てる（画面表示・Excel出力の両方で使う）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("SELECT id, title, is_anonymous FROM surveys WHERE id = %s"), (survey_id,))
    survey = cur.fetchone()
    if not survey:
        cur.close()
        conn.close()
        return None, 0, []

    cur.execute(
        fix(
            "SELECT id, question_text, question_type, choices FROM survey_questions "
            "WHERE survey_id = %s ORDER BY sort_order"
        ),
        (survey_id,),
    )
    questions = cur.fetchall()
    cur.execute(fix("SELECT COUNT(*) FROM survey_responses WHERE survey_id = %s"), (survey_id,))
    response_count = cur.fetchone()[0]

    results = []
    for q_id, q_text, q_type, choices_json in questions:
        cur.execute(fix("SELECT answer_text FROM survey_answers WHERE question_id = %s"), (q_id,))
        answers = [r[0] for r in cur.fetchall()]
        if q_type == "choice":
            choices = json.loads(choices_json) if choices_json else []
            counts = {c: 0 for c in choices}
            for a in answers:
                if a in counts:
                    counts[a] += 1
            results.append({"question": q_text, "type": "choice", "counts": counts})
        else:
            results.append({"question": q_text, "type": "free", "answers": [a for a in answers if a]})

    cur.close()
    conn.close()
    return survey, response_count, results


@bp.route("/admin/surveys/<int:survey_id>/results")
@admin_required
def survey_results(survey_id: int):
    survey, response_count, results = _build_results(survey_id)
    if not survey:
        flash("アンケートが見つかりません")
        return redirect(url_for("surveys.admin_surveys"))
    return render_template("surveys_results.html", survey=survey, response_count=response_count, results=results)


@bp.route("/admin/surveys/<int:survey_id>/results.xlsx")
@admin_required
def survey_results_excel(survey_id: int):
    survey, response_count, results = _build_results(survey_id)
    if not survey:
        flash("アンケートが見つかりません")
        return redirect(url_for("surveys.admin_surveys"))

    wb = Workbook()
    ws = wb.active
    ws.title = "集計結果"
    ws.append([survey[1]])
    ws.append([f"回答数: {response_count}"])
    ws.append([])
    for result in results:
        ws.append([result["question"]])
        if result["type"] == "choice":
            for choice, count in result["counts"].items():
                ws.append(["", choice, count])
        else:
            for answer in result["answers"]:
                ws.append(["", answer])
        ws.append([])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"survey_{survey_id}_results.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

`スタッフ管理/employee_portal/templates/surveys_admin.html`（操作列に結果・Excelリンクを追加、全文差し替え）:

```html
{% extends "base.html" %}
{% block content %}
<h2>アンケート管理</h2>
<form method="post" action="{{ url_for('surveys.create_survey') }}">
  <input type="text" name="title" placeholder="タイトル" required>
  <label><input type="checkbox" name="is_anonymous"> 匿名アンケートにする</label>
  <button type="submit">新規作成</button>
</form>
<table>
  <tr><th>タイトル</th><th>匿名</th><th>状態</th><th>操作</th></tr>
  {% for id, title, is_anonymous, is_open, created_at in surveys %}
  <tr>
    <td>{{ title }}</td>
    <td>{{ "匿名" if is_anonymous else "記名" }}</td>
    <td>{{ "公開中" if is_open else "下書き" }}</td>
    <td>
      <a href="{{ url_for('surveys.edit_survey', survey_id=id) }}">編集</a>
      <a href="{{ url_for('surveys.survey_results', survey_id=id) }}">結果</a>
      <a href="{{ url_for('surveys.survey_results_excel', survey_id=id) }}">Excel</a>
      {% if is_open %}
      <form method="post" action="{{ url_for('surveys.close_survey', survey_id=id) }}" style="display:inline">
        <button type="submit">締め切る</button>
      </form>
      {% else %}
      <form method="post" action="{{ url_for('surveys.publish_survey', survey_id=id) }}" style="display:inline">
        <button type="submit">公開する</button>
      </form>
      {% endif %}
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/surveys_results.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ survey[1] }} の集計結果</h2>
<p>回答数: {{ response_count }}</p>
{% for result in results %}
<h3>{{ result.question }}</h3>
{% if result.type == "choice" %}
<table>
  <tr><th>選択肢</th><th>件数</th></tr>
  {% for choice, count in result.counts.items() %}
  <tr><td>{{ choice }}</td><td>{{ count }}</td></tr>
  {% endfor %}
</table>
{% else %}
<ul>
  {% for answer in result.answers %}
  <li>{{ answer }}</li>
  {% endfor %}
</ul>
{% endif %}
{% endfor %}
<a href="{{ url_for('surveys.survey_results_excel', survey_id=survey[0]) }}">Excelでダウンロード</a>
{% endblock %}
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_survey_results.py -v`
Expected: PASS（2件成功）

- [ ] **Step 5: 既存テストも含めて全体を実行し、デグレがないことを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest -v`
Expected: PASS（全件成功）

- [ ] **Step 6: コミット**

```bash
git add "スタッフ管理/employee_portal/surveys.py" "スタッフ管理/employee_portal/templates/surveys_admin.html" "スタッフ管理/employee_portal/templates/surveys_results.html" "スタッフ管理/employee_portal/tests/test_survey_results.py"
git commit -m "feat(employee_portal): アンケート集計とExcel出力を追加"
```

---

## Task 7: 提案機能

**Files:**
- Create: `スタッフ管理/employee_portal/proposals.py`
- Modify: `スタッフ管理/employee_portal/app.py`
- Modify: `スタッフ管理/employee_portal/templates/admin_menu.html`
- Modify: `スタッフ管理/employee_portal/templates/employee_menu.html`
- Create: `スタッフ管理/employee_portal/templates/proposals_employee.html`
- Create: `スタッフ管理/employee_portal/templates/proposals_admin.html`
- Create: `スタッフ管理/employee_portal/tests/test_proposals.py`

**Interfaces:**
- Consumes: `auth.admin_required` / `auth.employee_required`（Task 2）, `db.get_conn` / `db.fix`（Task 1）
- Produces: Blueprint `proposals.bp`（`proposals.submit_proposal`, `proposals.admin_proposals`, `proposals.update_status`）, `proposals.STATUSES`

- [ ] **Step 1: 失敗するテストを書く**

`スタッフ管理/employee_portal/tests/test_proposals.py`:

```python
import db as db_module


def _login_admin(client):
    client.post("/login", data={"password": "admin123"})


def _add_employee_and_login(client, name="提案太郎"):
    _login_admin(client)
    client.post("/admin/employees/add", data={"name": name})
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM employees WHERE name = %s"), (name,))
    employee_id = cur.fetchone()[0]
    conn.close()

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})
    return employee_id


def test_named_proposal_is_linked_to_employee(client):
    employee_id = _add_employee_and_login(client)
    client.post("/proposals", data={"content": "レジ横の陳列を変えたい"}, follow_redirects=True)

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT employee_id, content FROM proposals WHERE content = %s"), ("レジ横の陳列を変えたい",))
    row = cur.fetchone()
    conn.close()
    assert row[0] == employee_id


def test_anonymous_proposal_does_not_store_employee_id(client):
    _add_employee_and_login(client)
    client.post(
        "/proposals",
        data={"content": "匿名の意見", "is_anonymous": "on"},
        follow_redirects=True,
    )

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT employee_id FROM proposals WHERE content = %s"), ("匿名の意見",))
    row = cur.fetchone()
    conn.close()
    assert row[0] is None


def test_admin_can_see_and_update_proposal_status(client):
    employee_id = _add_employee_and_login(client)
    client.post("/proposals", data={"content": "休憩室を改善したい"})

    client.get("/logout")
    _login_admin(client)
    resp = client.get("/admin/proposals")
    assert "休憩室を改善したい".encode("utf-8") in resp.data

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM proposals WHERE content = %s"), ("休憩室を改善したい",))
    proposal_id = cur.fetchone()[0]
    conn.close()

    client.post(f"/admin/proposals/{proposal_id}/status", data={"status": "対応中"}, follow_redirects=True)
    resp = client.get("/admin/proposals")
    assert "対応中".encode("utf-8") in resp.data
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_proposals.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'proposals'`、または404）

- [ ] **Step 3: `proposals.py`を実装し、`app.py`・メニュー画面を更新する**

`スタッフ管理/employee_portal/proposals.py`:

```python
"""提案投稿（従業員）・一覧管理（店長）"""
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth import admin_required, employee_required
from db import fix, get_conn

bp = Blueprint("proposals", __name__)

STATUSES = ["未対応", "対応中", "完了"]


@bp.route("/proposals", methods=["GET", "POST"])
@employee_required
def submit_proposal():
    if request.method == "POST":
        content = request.form.get("content", "").strip()
        is_anonymous = request.form.get("is_anonymous") == "on"
        if not content:
            flash("提案内容を入力してください")
            return redirect(url_for("proposals.submit_proposal"))

        employee_id = None if is_anonymous else session["employee_id"]
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            fix("INSERT INTO proposals (employee_id, content, status, created_at) VALUES (%s, %s, %s, %s)"),
            (employee_id, content, STATUSES[0], datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        cur.close()
        conn.close()
        flash("提案を送信しました")
        return redirect(url_for("proposals.submit_proposal"))

    return render_template("proposals_employee.html")


@bp.route("/admin/proposals")
@admin_required
def admin_proposals():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT proposals.id, employees.name, proposals.content, proposals.status, proposals.created_at
        FROM proposals
        LEFT JOIN employees ON employees.id = proposals.employee_id
        ORDER BY proposals.created_at DESC
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("proposals_admin.html", proposals=rows, statuses=STATUSES)


@bp.route("/admin/proposals/<int:proposal_id>/status", methods=["POST"])
@admin_required
def update_status(proposal_id: int):
    status = request.form.get("status", "")
    if status not in STATUSES:
        flash("不正なステータスです")
        return redirect(url_for("proposals.admin_proposals"))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(fix("UPDATE proposals SET status = %s WHERE id = %s"), (status, proposal_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("proposals.admin_proposals"))
```

`スタッフ管理/employee_portal/app.py`（`import surveys`の下に`import proposals`を追記し、blueprint登録を追加）:

```python
"""従業員ポータル Flask アプリケーション エントリポイント"""
import json
import logging
import os

from flask import Flask, redirect, render_template, session, url_for

import auth
import employees
import goals
import proposals
import surveys
from db import init_schema, load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    cfg = load_config()
    app.secret_key = cfg.get("secret_key", "dev-secret-change-me")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.jinja_env.filters["from_json"] = json.loads

    init_schema()

    app.register_blueprint(auth.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(goals.bp)
    app.register_blueprint(surveys.bp)
    app.register_blueprint(proposals.bp)

    @app.errorhandler(500)
    def handle_server_error(e):
        log.exception("予期しないエラーが発生しました")
        return render_template("error.html"), 500

    @app.route("/")
    def index():
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_menu"))
        if role == "employee":
            if session.get("employee_id"):
                return redirect(url_for("employee_menu"))
            return redirect(url_for("auth.select_employee"))
        return redirect(url_for("auth.login"))

    @app.route("/admin")
    @auth.admin_required
    def admin_menu():
        return render_template("admin_menu.html")

    @app.route("/employee")
    @auth.employee_required
    def employee_menu():
        return render_template("employee_menu.html", name=session.get("employee_name"))

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    create_app().run(host="0.0.0.0", port=port, debug=False)
```

`スタッフ管理/employee_portal/templates/admin_menu.html`（全文差し替え）:

```html
{% extends "base.html" %}
{% block content %}
<h2>店長メニュー</h2>
<ul>
  <li><a href="{{ url_for('employees.list_employees') }}">従業員マスタ管理</a></li>
  <li><a href="{{ url_for('goals.admin_goals') }}">目標・自己採点</a></li>
  <li><a href="{{ url_for('surveys.admin_surveys') }}">アンケート管理</a></li>
  <li><a href="{{ url_for('proposals.admin_proposals') }}">提案一覧</a></li>
</ul>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/employee_menu.html`（全文差し替え）:

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ name }} さん、こんにちは</h2>
<ul>
  <li><a href="{{ url_for('goals.my_goals') }}">目標の自己採点</a></li>
  <li><a href="{{ url_for('surveys.list_surveys') }}">アンケートに回答</a></li>
  <li><a href="{{ url_for('proposals.submit_proposal') }}">提案する</a></li>
</ul>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/proposals_employee.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>提案する</h2>
<form method="post">
  <textarea name="content" placeholder="提案内容" required></textarea>
  <label><input type="checkbox" name="is_anonymous"> 匿名で送る</label>
  <button type="submit">送信</button>
</form>
{% endblock %}
```

`スタッフ管理/employee_portal/templates/proposals_admin.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>提案一覧</h2>
<table>
  <tr><th>日時</th><th>投稿者</th><th>内容</th><th>ステータス</th></tr>
  {% for id, name, content, status, created_at in proposals %}
  <tr>
    <td>{{ created_at }}</td>
    <td>{{ name or "匿名" }}</td>
    <td>{{ content }}</td>
    <td>
      <form method="post" action="{{ url_for('proposals.update_status', proposal_id=id) }}">
        <select name="status" onchange="this.form.submit()">
          {% for s in statuses %}
          <option value="{{ s }}" {{ "selected" if s == status else "" }}>{{ s }}</option>
          {% endfor %}
        </select>
      </form>
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest tests/test_proposals.py -v`
Expected: PASS（3件成功）

- [ ] **Step 5: 全テストを実行し、デグレがないことを確認する**

Run: `cd "スタッフ管理/employee_portal" && python -m pytest -v`
Expected: PASS（全件成功）

- [ ] **Step 6: コミット**

```bash
git add "スタッフ管理/employee_portal/proposals.py" "スタッフ管理/employee_portal/app.py" "スタッフ管理/employee_portal/templates/admin_menu.html" "スタッフ管理/employee_portal/templates/employee_menu.html" "スタッフ管理/employee_portal/templates/proposals_employee.html" "スタッフ管理/employee_portal/templates/proposals_admin.html" "スタッフ管理/employee_portal/tests/test_proposals.py"
git commit -m "feat(employee_portal): 提案機能を追加"
```

---

## Task 8: デプロイ準備・ドキュメント整備

**Files:**
- Create: `スタッフ管理/employee_portal/Procfile`
- Create: `スタッフ管理/employee_portal/README.md`

**Interfaces:**
- Consumes: Task 1〜7の全成果物
- Produces: なし（デプロイ手順・動作確認手順のドキュメント）

- [ ] **Step 1: `Procfile`を作成する**

`スタッフ管理/employee_portal/Procfile`:

```
web: gunicorn "app:create_app()"
```

- [ ] **Step 2: `README.md`を作成する**

`スタッフ管理/employee_portal/README.md`:

```markdown
# 従業員ポータル（天理店）

目標の自己採点・アンケート（匿名/記名）・提案（匿名/記名）をまとめたWebアプリ。
設計書: `docs/superpowers/specs/2026-09-23-employee-portal-design.md`

## セットアップ（ローカル）

```powershell
cd スタッフ管理\employee_portal
pip install -r requirements.txt -r requirements-dev.txt
copy config.example.json config.json
# config.json を開いて admin_password / general_password / secret_key を設定する
python app.py
```

ブラウザで `http://localhost:5000` を開く。`config.json`の`db_url`が空の場合はSQLite
（`employee_portal.db`）が自動的に使われる。

## テスト実行

```powershell
cd スタッフ管理\employee_portal
python -m pytest -v
```

## Supabase（本番DB）を使う場合

`config.json`の`db_url`にSupabaseの接続文字列を設定すると、自動的にPostgreSQLへ
切り替わる（起動時にテーブルが自動作成される）。POSシステムと同じSupabase
プロジェクトに、`employees` / `goals` / `goal_scores` / `surveys` /
`survey_questions` / `survey_responses` / `survey_answers` / `proposals`
の8テーブルが新規作成される（既存のPOSテーブルとは無関係）。

## Renderへのデプロイ

1. このリポジトリをRenderの「Web Service」として登録する
   （Root Directory: `スタッフ管理/employee_portal`）
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn "app:create_app()"`（`Procfile`があれば自動検出される）
4. Renderの「Environment」で以下の環境変数を設定する（`config.json`はGit管理外の
   ため、本番ではこちらを使う）
   - `EMPLOYEE_PORTAL_DB_URL`: SupabaseのPostgreSQL接続文字列
   - `EMPLOYEE_PORTAL_ADMIN_PASSWORD`: 店長用パスワード
   - `EMPLOYEE_PORTAL_GENERAL_PASSWORD`: 従業員共通パスワード
   - `EMPLOYEE_PORTAL_SECRET_KEY`: セッション用のランダムな文字列
5. デプロイ後、初回アクセス時に`init_schema()`が実行され、Supabase上にテーブルが
   自動作成される

## 手動での動作確認手順

1. 店長メニューから従業員を1名登録する
2. 同じ従業員に目標を1件登録する
3. 従業員としてログインし、名前を選択して目標に自己採点する
4. 店長メニューの「採点履歴」で記録が見えることを確認する
5. 店長メニューからアンケートを新規作成し、自由記述・選択式の質問を1問ずつ追加して
   公開する
6. 従業員としてアンケートに回答する
7. 店長メニューの「結果」で集計を確認し、「Excel」からダウンロードできることを
   確認する
8. 従業員として記名・匿名それぞれで提案を送信し、店長メニューの「提案一覧」で
   投稿者表示（匿名は「匿名」と表示）とステータス変更ができることを確認する
```

- [ ] **Step 3: コミット**

```bash
git add "スタッフ管理/employee_portal/Procfile" "スタッフ管理/employee_portal/README.md"
git commit -m "docs(employee_portal): デプロイ手順・動作確認手順を追加"
```

---

## 完了確認

- [ ] `cd "スタッフ管理/employee_portal" && python -m pytest -v` が全件成功する
- [ ] `python app.py` でローカル起動し、README「手動での動作確認手順」を一通り実施する
- [ ] `config.json`が`.gitignore`によりコミットされていないことを`git status`で確認する
