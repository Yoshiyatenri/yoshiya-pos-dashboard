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
