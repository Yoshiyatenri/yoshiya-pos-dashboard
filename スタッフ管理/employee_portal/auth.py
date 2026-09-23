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
