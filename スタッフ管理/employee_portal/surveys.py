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
