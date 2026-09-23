import db as db_module


def _login_admin(client):
    client.post("/login", data={"password": "admin123"})


def _create_published_survey_with_choice_question(client):
    _login_admin(client)
    client.post("/admin/surveys/create", data={"title": "休憩時間アンケート"})
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM surveys WHERE title = %s"), ("休憩時間アンケート",))
    survey_id = cur.fetchone()[0]
    conn.close()

    client.post(
        f"/admin/surveys/{survey_id}/questions/add",
        data={"question_text": "休憩時間は十分？", "question_type": "choice", "choices": "十分,やや不足,不足"},
    )
    client.post(f"/admin/surveys/{survey_id}/publish")
    return survey_id


def _create_published_anonymous_survey_with_free_question(client, title="匿名意見アンケート"):
    _login_admin(client)
    client.post("/admin/surveys/create", data={"title": title, "is_anonymous": "on"})
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM surveys WHERE title = %s"), (title,))
    survey_id = cur.fetchone()[0]
    conn.close()

    client.post(
        f"/admin/surveys/{survey_id}/questions/add",
        data={"question_text": "率直な意見", "question_type": "free"},
    )
    client.post(f"/admin/surveys/{survey_id}/publish")
    return survey_id


def _answer_as_new_employee(client, survey_id, name, answer_map):
    client.post("/admin/employees/add", data={"name": name})
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM employees WHERE name = %s"), (name,))
    employee_id = cur.fetchone()[0]
    conn.close()

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})
    client.post(f"/surveys/{survey_id}/answer", data=answer_map)
    client.get("/logout")
    _login_admin(client)


def test_results_page_shows_choice_counts(client):
    survey_id = _create_published_survey_with_choice_question(client)
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM survey_questions WHERE survey_id = %s"), (survey_id,))
    question_id = cur.fetchone()[0]
    conn.close()

    _answer_as_new_employee(client, survey_id, "回答者A", {f"question_{question_id}": "十分"})
    _answer_as_new_employee(client, survey_id, "回答者B", {f"question_{question_id}": "不足"})

    resp = client.get(f"/admin/surveys/{survey_id}/results")
    assert "回答数: 2".encode("utf-8") in resp.data
    assert "十分".encode("utf-8") in resp.data


def test_results_excel_download_returns_xlsx(client):
    survey_id = _create_published_survey_with_choice_question(client)
    resp = client.get(f"/admin/surveys/{survey_id}/results.xlsx")
    assert resp.status_code == 200
    assert resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_results_page_shows_respondent_name_for_named_survey(client):
    survey_id = _create_published_survey_with_choice_question(client)
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM survey_questions WHERE survey_id = %s"), (survey_id,))
    question_id = cur.fetchone()[0]
    conn.close()

    _answer_as_new_employee(client, survey_id, "山田花子", {f"question_{question_id}": "十分"})

    resp = client.get(f"/admin/surveys/{survey_id}/results")
    assert "山田花子".encode("utf-8") in resp.data


def test_build_results_groups_answers_by_individual_response(client):
    _login_admin(client)
    client.post("/admin/surveys/create", data={"title": "複数質問アンケート"})
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM surveys WHERE title = %s"), ("複数質問アンケート",))
    survey_id = cur.fetchone()[0]
    conn.close()

    client.post(
        f"/admin/surveys/{survey_id}/questions/add", data={"question_text": "感想", "question_type": "free"}
    )
    client.post(
        f"/admin/surveys/{survey_id}/questions/add",
        data={"question_text": "満足度", "question_type": "choice", "choices": "満足,普通,不満"},
    )
    client.post(f"/admin/surveys/{survey_id}/publish")

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(
        db_module.fix("SELECT id, question_text FROM survey_questions WHERE survey_id = %s ORDER BY sort_order"),
        (survey_id,),
    )
    kanso_id, manzoku_id = [r[0] for r in cur.fetchall()]
    conn.close()

    _answer_as_new_employee(
        client, survey_id, "山田花子",
        {f"question_{kanso_id}": "とても良かった", f"question_{manzoku_id}": "満足"},
    )
    _answer_as_new_employee(
        client, survey_id, "鈴木一郎",
        {f"question_{kanso_id}": "普通でした", f"question_{manzoku_id}": "普通"},
    )

    import surveys
    _, _, _, individual_responses = surveys._build_results(survey_id)

    assert len(individual_responses) == 2
    by_name = {r["respondent"]: dict(r["answers"]) for r in individual_responses}
    assert by_name["山田花子"] == {"感想": "とても良かった", "満足度": "満足"}
    assert by_name["鈴木一郎"] == {"感想": "普通でした", "満足度": "普通"}


def test_build_results_individual_response_has_no_respondent_for_anonymous_survey(client):
    survey_id = _create_published_anonymous_survey_with_free_question(client)
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM survey_questions WHERE survey_id = %s"), (survey_id,))
    question_id = cur.fetchone()[0]
    conn.close()

    _answer_as_new_employee(client, survey_id, "鈴木一郎", {f"question_{question_id}": "特になし"})

    import surveys
    _, _, _, individual_responses = surveys._build_results(survey_id)

    assert len(individual_responses) == 1
    assert individual_responses[0]["respondent"] is None
    assert individual_responses[0]["answers"] == [("率直な意見", "特になし")]


def test_results_page_shows_individual_responses_table(client):
    survey_id = _create_published_survey_with_choice_question(client)
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM survey_questions WHERE survey_id = %s"), (survey_id,))
    question_id = cur.fetchone()[0]
    conn.close()

    _answer_as_new_employee(client, survey_id, "山田花子", {f"question_{question_id}": "十分"})

    resp = client.get(f"/admin/surveys/{survey_id}/results")
    assert "個別回答一覧".encode("utf-8") in resp.data
    assert "山田花子".encode("utf-8") in resp.data


def test_results_page_hides_respondent_list_for_anonymous_survey(client):
    survey_id = _create_published_anonymous_survey_with_free_question(client)
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM survey_questions WHERE survey_id = %s"), (survey_id,))
    question_id = cur.fetchone()[0]
    conn.close()

    _answer_as_new_employee(client, survey_id, "鈴木一郎", {f"question_{question_id}": "特になし"})

    resp = client.get(f"/admin/surveys/{survey_id}/results")
    assert "鈴木一郎".encode("utf-8") not in resp.data
