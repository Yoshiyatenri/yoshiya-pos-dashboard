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
