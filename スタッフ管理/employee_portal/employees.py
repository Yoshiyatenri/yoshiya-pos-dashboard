"""従業員マスタ管理（店長のみ）"""
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from auth import admin_required
from db import db_cursor, fix

bp = Blueprint("employees", __name__, url_prefix="/admin/employees")


@bp.route("/")
@admin_required
def list_employees():
    with db_cursor() as cur:
        cur.execute("SELECT id, name, is_active FROM employees ORDER BY name")
        rows = cur.fetchall()
    return render_template("employees_admin.html", employees=rows)


@bp.route("/add", methods=["POST"])
@admin_required
def add_employee():
    name = request.form.get("name", "").strip()
    if not name:
        flash("名前を入力してください")
        return redirect(url_for("employees.list_employees"))
    with db_cursor(commit=True) as cur:
        cur.execute(
            fix("INSERT INTO employees (name, is_active, created_at) VALUES (%s, 1, %s)"),
            (name, datetime.now(timezone.utc).isoformat()),
        )
    flash(f"{name} さんを登録しました")
    return redirect(url_for("employees.list_employees"))


@bp.route("/<int:employee_id>/deactivate", methods=["POST"])
@admin_required
def deactivate_employee(employee_id: int):
    with db_cursor(commit=True) as cur:
        cur.execute(fix("UPDATE employees SET is_active = 0 WHERE id = %s"), (employee_id,))
    return redirect(url_for("employees.list_employees"))


@bp.route("/<int:employee_id>/activate", methods=["POST"])
@admin_required
def activate_employee(employee_id: int):
    with db_cursor(commit=True) as cur:
        cur.execute(fix("UPDATE employees SET is_active = 1 WHERE id = %s"), (employee_id,))
    return redirect(url_for("employees.list_employees"))
