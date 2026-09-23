"""目標管理（店長）・自己採点（従業員）"""
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth import admin_required, employee_required
from db import db_cursor, fix

bp = Blueprint("goals", __name__)

VALID_SCORES = {str(n) for n in range(0, 11)}


@bp.route("/admin/goals")
@admin_required
def admin_goals():
    with db_cursor() as cur:
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
    return render_template("goals_admin.html", employees=employees, goals=goal_rows)


@bp.route("/admin/goals/add", methods=["POST"])
@admin_required
def add_goal():
    employee_id = request.form.get("employee_id", "")
    raw_text = request.form.get("goal_text", "")
    goal_texts = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not employee_id or not goal_texts:
        flash("従業員と目標内容を入力してください")
        return redirect(url_for("goals.admin_goals"))
    with db_cursor(commit=True) as cur:
        for goal_text in goal_texts:
            cur.execute(
                fix("INSERT INTO goals (employee_id, goal_text, is_active, created_at) VALUES (%s, %s, 1, %s)"),
                (employee_id, goal_text, datetime.now(timezone.utc).isoformat()),
            )
    flash(f"目標を{len(goal_texts)}件登録しました")
    return redirect(url_for("goals.admin_goals"))


@bp.route("/admin/goals/<int:goal_id>/deactivate", methods=["POST"])
@admin_required
def deactivate_goal(goal_id: int):
    with db_cursor(commit=True) as cur:
        cur.execute(fix("UPDATE goals SET is_active = 0 WHERE id = %s"), (goal_id,))
    return redirect(url_for("goals.admin_goals"))


@bp.route("/admin/goals/<int:employee_id>/scores")
@admin_required
def admin_goal_scores(employee_id: int):
    with db_cursor() as cur:
        cur.execute(fix("SELECT id, goal_text FROM goals WHERE employee_id = %s ORDER BY created_at"), (employee_id,))
        goals_list = cur.fetchall()
        scores_by_goal = {}
        for goal_id, _ in goals_list:
            cur.execute(
                fix("SELECT score, comment, scored_at FROM goal_scores WHERE goal_id = %s ORDER BY scored_at"),
                (goal_id,),
            )
            scores_by_goal[goal_id] = cur.fetchall()
    return render_template("goal_scores_admin.html", goals=goals_list, scores_by_goal=scores_by_goal)


@bp.route("/goals", methods=["GET", "POST"])
@employee_required
def my_goals():
    employee_id = session["employee_id"]
    with db_cursor(commit=True) as cur:
        cur.execute(
            fix("SELECT id, goal_text FROM goals WHERE employee_id = %s AND is_active = 1 ORDER BY created_at"),
            (employee_id,),
        )
        goals_list = cur.fetchall()

        if request.method == "POST":
            # 自分の目標だけを対象にする（他人のgoal_idを送られても無視される）
            entries = []
            for goal_id, _ in goals_list:
                score = request.form.get(f"score_{goal_id}", "").strip()
                if not score:
                    continue
                if score not in VALID_SCORES:
                    flash("評価は0〜10で選んでください")
                    return redirect(url_for("goals.my_goals"))
                comment = request.form.get(f"comment_{goal_id}", "").strip()
                entries.append((goal_id, score, comment))

            if not entries:
                flash("採点する目標を選択してください")
                return redirect(url_for("goals.my_goals"))

            now = datetime.now(timezone.utc).isoformat()
            for goal_id, score, comment in entries:
                cur.execute(
                    fix("INSERT INTO goal_scores (goal_id, score, comment, scored_at) VALUES (%s, %s, %s, %s)"),
                    (goal_id, int(score), comment, now),
                )
            flash("採点を記録しました")
            return redirect(url_for("goals.my_goals"))

    return render_template("goals_employee.html", goals=goals_list)
