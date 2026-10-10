import re

import db as db_module


def _login_admin(client):
    client.post("/login", data={"password": "admin123"})


def _add_employee_and_login(client, name="採点太郎"):
    _login_admin(client)
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


def _goal_ids_for(employee_id):
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(
        db_module.fix("SELECT id FROM goals WHERE employee_id = %s ORDER BY id"), (employee_id,)
    )
    ids = [r[0] for r in cur.fetchall()]
    conn.close()
    return ids


def test_admin_can_add_goal_for_employee(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    resp = client.post(
        "/admin/goals/add",
        data={"employee_id": str(employee_id), "goal_text": "接客満足度を上げる"},
        follow_redirects=True,
    )
    assert "接客満足度を上げる".encode("utf-8") in resp.data


def test_admin_can_add_multiple_goals_at_once(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    resp = client.post(
        "/admin/goals/add",
        data={
            "employee_id": str(employee_id),
            "goal_text": "接客満足度を上げる\n品出しを早くする\nレジ締めを正確にする",
        },
        follow_redirects=True,
    )
    assert "接客満足度を上げる".encode("utf-8") in resp.data
    assert "品出しを早くする".encode("utf-8") in resp.data
    assert "レジ締めを正確にする".encode("utf-8") in resp.data
    assert len(_goal_ids_for(employee_id)) == 3


def test_blank_lines_in_multi_goal_input_are_ignored(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post(
        "/admin/goals/add",
        data={"employee_id": str(employee_id), "goal_text": "目標A\n\n \n目標B\n"},
        follow_redirects=True,
    )
    assert len(_goal_ids_for(employee_id)) == 2


def test_employee_sees_own_goals(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "品出しを早くする"})

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    resp = client.get("/goals")
    assert "品出しを早くする".encode("utf-8") in resp.data


def test_employee_can_score_multiple_goals_in_one_submission(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "目標A\n目標B"})
    goal_a_id, goal_b_id = _goal_ids_for(employee_id)

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    resp = client.post(
        "/goals",
        data={
            f"score_{goal_a_id}": "3",
            f"comment_{goal_a_id}": "目標Aのコメント",
            f"score_{goal_b_id}": "8",
            f"comment_{goal_b_id}": "目標Bのコメント",
        },
        follow_redirects=True,
    )
    assert "採点を記録しました".encode("utf-8") in resp.data

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT score, comment FROM goal_scores WHERE goal_id = %s"), (goal_a_id,))
    score_a, comment_a = cur.fetchone()
    cur.execute(db_module.fix("SELECT score, comment FROM goal_scores WHERE goal_id = %s"), (goal_b_id,))
    score_b, comment_b = cur.fetchone()
    conn.close()
    assert score_a == 3
    assert comment_a == "目標Aのコメント"
    assert score_b == 8
    assert comment_b == "目標Bのコメント"


def test_leaving_a_goal_blank_does_not_record_a_score_for_it(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "目標A\n目標B"})
    goal_a_id, goal_b_id = _goal_ids_for(employee_id)

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    client.post(
        "/goals",
        data={f"score_{goal_a_id}": "5", f"comment_{goal_a_id}": "Aだけ採点"},
        follow_redirects=True,
    )

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT COUNT(*) FROM goal_scores WHERE goal_id = %s"), (goal_a_id,))
    count_a = cur.fetchone()[0]
    cur.execute(db_module.fix("SELECT COUNT(*) FROM goal_scores WHERE goal_id = %s"), (goal_b_id,))
    count_b = cur.fetchone()[0]
    conn.close()
    assert count_a == 1
    assert count_b == 0


def test_score_of_0_is_accepted(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "目標X"})
    (goal_id,) = _goal_ids_for(employee_id)

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    resp = client.post("/goals", data={f"score_{goal_id}": "0"}, follow_redirects=True)
    assert "採点を記録しました".encode("utf-8") in resp.data


def test_score_of_10_is_accepted(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "目標X"})
    (goal_id,) = _goal_ids_for(employee_id)

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    resp = client.post("/goals", data={f"score_{goal_id}": "10"}, follow_redirects=True)
    assert "採点を記録しました".encode("utf-8") in resp.data


def test_invalid_score_in_batch_rejects_whole_submission(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "目標A\n目標B"})
    goal_a_id, goal_b_id = _goal_ids_for(employee_id)

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    resp = client.post(
        "/goals",
        data={f"score_{goal_a_id}": "5", f"score_{goal_b_id}": "11"},
        follow_redirects=True,
    )
    assert "評価は0〜10で選んでください".encode("utf-8") in resp.data

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT COUNT(*) FROM goal_scores WHERE goal_id = %s"), (goal_a_id,))
    count_a = cur.fetchone()[0]
    conn.close()
    assert count_a == 0


def test_score_history_shows_simplified_datetime(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "目標X"})
    (goal_id,) = _goal_ids_for(employee_id)

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})
    client.post("/goals", data={f"score_{goal_id}": "7"}, follow_redirects=True)

    client.get("/logout")
    _login_admin(client)
    resp = client.get(f"/admin/goals/{employee_id}/scores")

    assert b"+00:00" not in resp.data
    assert re.search(rb"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", resp.data)


def test_score_history_excludes_deactivated_goals(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post(
        "/admin/goals/add",
        data={"employee_id": str(employee_id), "goal_text": "有効な目標\n終了した目標"},
    )
    goal_active_id, goal_inactive_id = _goal_ids_for(employee_id)
    client.post(f"/admin/goals/{goal_inactive_id}/deactivate")

    resp = client.get(f"/admin/goals/{employee_id}/scores")
    assert "有効な目標".encode("utf-8") in resp.data
    assert "終了した目標".encode("utf-8") not in resp.data


def test_employee_cannot_score_other_employees_goal(client):
    employee_a = _add_employee_and_login(client, name="Aさん")
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_a), "goal_text": "Aさんの目標"})
    client.post("/admin/employees/add", data={"name": "Bさん"})

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM employees WHERE name = %s"), ("Bさん",))
    employee_b = cur.fetchone()[0]
    conn.close()
    (goal_id,) = _goal_ids_for(employee_a)

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_b)})

    client.post(
        "/goals",
        data={f"score_{goal_id}": "5", f"comment_{goal_id}": "なりすまし"},
        follow_redirects=True,
    )

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT COUNT(*) FROM goal_scores WHERE goal_id = %s"), (goal_id,))
    count = cur.fetchone()[0]
    conn.close()
    assert count == 0
