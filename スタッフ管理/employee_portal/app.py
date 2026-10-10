"""従業員ポータル Flask アプリケーション エントリポイント"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from flask import Flask, redirect, render_template, session, url_for

JST = timezone(timedelta(hours=9))


def format_datetime(value):
    """ISO形式の日時文字列を「YYYY-MM-DD HH:MM」(日本時間)の簡潔な表示に変換する"""
    if not value:
        return value
    return datetime.fromisoformat(value).astimezone(JST).strftime("%Y-%m-%d %H:%M")

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
    secret = cfg.get("secret_key")
    if not secret or secret == "CHANGE_ME":
        raise RuntimeError("secret_key が未設定です。config.json または EMPLOYEE_PORTAL_SECRET_KEY を設定してください")
    app.secret_key = secret
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.jinja_env.filters["from_json"] = json.loads
    app.jinja_env.filters["format_datetime"] = format_datetime

    try:
        init_schema()
    except Exception:
        log.exception("起動時のDB初期化に失敗しました")

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
