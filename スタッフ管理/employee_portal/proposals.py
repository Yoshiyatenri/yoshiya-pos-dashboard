"""提案投稿（従業員）・一覧管理（店長）"""
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth import admin_required, employee_required
from db import db_cursor, fix

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
        with db_cursor(commit=True) as cur:
            cur.execute(
                fix("INSERT INTO proposals (employee_id, content, status, created_at) VALUES (%s, %s, %s, %s)"),
                (employee_id, content, STATUSES[0], datetime.now(timezone.utc).isoformat()),
            )
        flash("提案を送信しました")
        return redirect(url_for("proposals.submit_proposal"))

    return render_template("proposals_employee.html")


@bp.route("/admin/proposals")
@admin_required
def admin_proposals():
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT proposals.id, employees.name, proposals.content, proposals.status, proposals.created_at
            FROM proposals
            LEFT JOIN employees ON employees.id = proposals.employee_id
            ORDER BY proposals.created_at DESC
            """
        )
        rows = cur.fetchall()
    return render_template("proposals_admin.html", proposals=rows, statuses=STATUSES)


@bp.route("/admin/proposals/<int:proposal_id>/status", methods=["POST"])
@admin_required
def update_status(proposal_id: int):
    status = request.form.get("status", "")
    if status not in STATUSES:
        flash("不正なステータスです")
        return redirect(url_for("proposals.admin_proposals"))
    with db_cursor(commit=True) as cur:
        cur.execute(fix("UPDATE proposals SET status = %s WHERE id = %s"), (status, proposal_id))
    return redirect(url_for("proposals.admin_proposals"))
