"""アンケート作成（店長）・回答（従業員）・集計・Excel出力"""
import json
from datetime import datetime, timezone
from io import BytesIO

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from openpyxl import Workbook

from auth import admin_required, employee_required
from db import db_cursor, fix, insert_returning_id

bp = Blueprint("surveys", __name__)


@bp.route("/admin/surveys")
@admin_required
def admin_surveys():
    with db_cursor() as cur:
        cur.execute("SELECT id, title, is_anonymous, is_open, created_at FROM surveys ORDER BY created_at DESC")
        rows = cur.fetchall()
    return render_template("surveys_admin.html", surveys=rows)


@bp.route("/admin/surveys/create", methods=["POST"])
@admin_required
def create_survey():
    title = request.form.get("title", "").strip()
    is_anonymous = 1 if request.form.get("is_anonymous") == "on" else 0
    if not title:
        flash("タイトルを入力してください")
        return redirect(url_for("surveys.admin_surveys"))

    with db_cursor(commit=True) as cur:
        survey_id = insert_returning_id(
            cur,
            "INSERT INTO surveys (title, is_anonymous, is_open, created_at) VALUES (%s, %s, 0, %s)",
            (title, is_anonymous, datetime.now(timezone.utc).isoformat()),
        )
    return redirect(url_for("surveys.edit_survey", survey_id=survey_id))


@bp.route("/admin/surveys/<int:survey_id>/edit")
@admin_required
def edit_survey(survey_id: int):
    with db_cursor() as cur:
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

    with db_cursor(commit=True) as cur:
        cur.execute(
            fix("SELECT COALESCE(MAX(sort_order), -1) FROM survey_questions WHERE survey_id = %s"), (survey_id,)
        )
        next_order = cur.fetchone()[0] + 1
        cur.execute(
            fix(
                "INSERT INTO survey_questions (survey_id, question_text, question_type, choices, sort_order) "
                "VALUES (%s, %s, %s, %s, %s)"
            ),
            (survey_id, question_text, question_type, choices_json, next_order),
        )
    return redirect(url_for("surveys.edit_survey", survey_id=survey_id))


@bp.route("/admin/surveys/<int:survey_id>/publish", methods=["POST"])
@admin_required
def publish_survey(survey_id: int):
    with db_cursor(commit=True) as cur:
        cur.execute(fix("UPDATE surveys SET is_open = 1 WHERE id = %s"), (survey_id,))
    flash("アンケートを公開しました")
    return redirect(url_for("surveys.admin_surveys"))


@bp.route("/admin/surveys/<int:survey_id>/close", methods=["POST"])
@admin_required
def close_survey(survey_id: int):
    with db_cursor(commit=True) as cur:
        cur.execute(fix("UPDATE surveys SET is_open = 0 WHERE id = %s"), (survey_id,))
    flash("アンケートを締め切りました")
    return redirect(url_for("surveys.admin_surveys"))


@bp.route("/surveys")
@employee_required
def list_surveys():
    with db_cursor() as cur:
        cur.execute("SELECT id, title FROM surveys WHERE is_open = 1 ORDER BY created_at DESC")
        open_surveys = cur.fetchall()
    return render_template("surveys_list.html", surveys=open_surveys)


@bp.route("/surveys/<int:survey_id>/answer", methods=["GET", "POST"])
@employee_required
def answer_survey(survey_id: int):
    with db_cursor(commit=True) as cur:
        cur.execute(fix("SELECT id, title, is_anonymous, is_open FROM surveys WHERE id = %s"), (survey_id,))
        survey = cur.fetchone()
        if not survey or survey[3] != 1:
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
            # 選択式の質問は、送信された値が選択肢に含まれているかサーバー側でも確認する
            for q_id, _, q_type, choices_json in questions:
                if q_type == "choice":
                    choices = json.loads(choices_json)
                    answer_text = request.form.get(f"question_{q_id}", "").strip()
                    if answer_text not in choices:
                        flash("選択肢の中から選んでください")
                        return redirect(url_for("surveys.answer_survey", survey_id=survey_id))

            # 記名アンケートは、同じ従業員が二重に回答できないようにする（匿名は対象外）
            if not survey[2]:
                cur.execute(
                    fix("SELECT id FROM survey_responses WHERE survey_id = %s AND employee_id = %s"),
                    (survey_id, session["employee_id"]),
                )
                if cur.fetchone():
                    flash("既に回答済みです")
                    return redirect(url_for("surveys.list_surveys"))

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
            flash("回答ありがとうございました")
            return redirect(url_for("surveys.list_surveys"))

    return render_template("surveys_answer.html", survey=survey, questions=questions)


def _build_results(survey_id: int):
    """アンケートの集計結果を組み立てる（画面表示・Excel出力の両方で使う）"""
    with db_cursor() as cur:
        cur.execute(fix("SELECT id, title, is_anonymous FROM surveys WHERE id = %s"), (survey_id,))
        survey = cur.fetchone()
        if not survey:
            return None, 0, [], []

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

        # 個別回答一覧（1回答＝1件として、その回答内の全質問への回答をまとめる）
        # 匿名の回答はemployee_idがNULLのため、LEFT JOINしても回答者名は取得されない
        cur.execute(
            fix(
                "SELECT survey_responses.id, employees.name FROM survey_responses "
                "LEFT JOIN employees ON employees.id = survey_responses.employee_id "
                "WHERE survey_responses.survey_id = %s ORDER BY survey_responses.submitted_at"
            ),
            (survey_id,),
        )
        response_rows = cur.fetchall()

        individual_responses = []
        for response_id, respondent_name in response_rows:
            cur.execute(
                fix(
                    "SELECT survey_questions.question_text, survey_answers.answer_text "
                    "FROM survey_answers "
                    "JOIN survey_questions ON survey_questions.id = survey_answers.question_id "
                    "WHERE survey_answers.response_id = %s "
                    "ORDER BY survey_questions.sort_order"
                ),
                (response_id,),
            )
            individual_responses.append({"respondent": respondent_name, "answers": cur.fetchall()})

    return survey, response_count, results, individual_responses


@bp.route("/admin/surveys/<int:survey_id>/results")
@admin_required
def survey_results(survey_id: int):
    survey, response_count, results, individual_responses = _build_results(survey_id)
    if not survey:
        flash("アンケートが見つかりません")
        return redirect(url_for("surveys.admin_surveys"))
    return render_template(
        "surveys_results.html",
        survey=survey,
        response_count=response_count,
        results=results,
        individual_responses=individual_responses,
    )


@bp.route("/admin/surveys/<int:survey_id>/results.xlsx")
@admin_required
def survey_results_excel(survey_id: int):
    survey, response_count, results, individual_responses = _build_results(survey_id)
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

    ws2 = wb.create_sheet("個別回答")
    ws2.append(["回答者"] + [r["question"] for r in results])
    for response in individual_responses:
        ws2.append([response["respondent"] or "匿名"] + [answer_text for _, answer_text in response["answers"]])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"survey_{survey_id}_results.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
