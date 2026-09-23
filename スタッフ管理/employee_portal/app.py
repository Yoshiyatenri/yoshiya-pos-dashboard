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
