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


def test_employee_sees_own_goal_and_can_score_it(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "品出しを早くする"})

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    resp = client.get("/goals")
    assert "品出しを早くする".encode("utf-8") in resp.data

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM goals WHERE employee_id = %s"), (employee_id,))
    goal_id = cur.fetchone()[0]
    conn.close()

    resp = client.post(
        f"/goals/{goal_id}/score",
        data={"score": "4", "comment": "だいぶ早くなった"},
        follow_redirects=True,
    )
    assert "採点を記録しました".encode("utf-8") in resp.data


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

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT COUNT(*) FROM goals WHERE employee_id = %s"), (employee_id,))
    count = cur.fetchone()[0]
    conn.close()
    assert count == 3


def test_blank_lines_in_multi_goal_input_are_ignored(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post(
        "/admin/goals/add",
        data={"employee_id": str(employee_id), "goal_text": "目標A\n\n \n目標B\n"},
        follow_redirects=True,
    )

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT COUNT(*) FROM goals WHERE employee_id = %s"), (employee_id,))
    count = cur.fetchone()[0]
    conn.close()
    assert count == 2


def test_goals_added_in_batch_can_be_scored_independently(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post(
        "/admin/goals/add",
        data={"employee_id": str(employee_id), "goal_text": "目標A\n目標B"},
    )

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(
        db_module.fix("SELECT id, goal_text FROM goals WHERE employee_id = %s ORDER BY id"), (employee_id,)
    )
    rows = cur.fetchall()
    conn.close()
    assert len(rows) == 2
    goal_a_id = rows[0][0]
    goal_b_id = rows[1][0]

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})
    resp = client.post(
        f"/goals/{goal_a_id}/score",
        data={"score": "3", "comment": "目標Aだけ採点"},
        follow_redirects=True,
    )
    assert "採点を記録しました".encode("utf-8") in resp.data

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

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM goals WHERE employee_id = %s"), (employee_id,))
    goal_id = cur.fetchone()[0]
    conn.close()

    resp = client.post(f"/goals/{goal_id}/score", data={"score": "0", "comment": ""}, follow_redirects=True)
    assert "採点を記録しました".encode("utf-8") in resp.data


def test_score_of_10_is_accepted(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "目標X"})

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM goals WHERE employee_id = %s"), (employee_id,))
    goal_id = cur.fetchone()[0]
    conn.close()

    resp = client.post(f"/goals/{goal_id}/score", data={"score": "10", "comment": ""}, follow_redirects=True)
    assert "採点を記録しました".encode("utf-8") in resp.data


def test_score_of_11_is_rejected(client):
    employee_id = _add_employee_and_login(client)
    client.get("/logout")
    _login_admin(client)
    client.post("/admin/goals/add", data={"employee_id": str(employee_id), "goal_text": "目標X"})

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_id)})

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM goals WHERE employee_id = %s"), (employee_id,))
    goal_id = cur.fetchone()[0]
    conn.close()

    resp = client.post(f"/goals/{goal_id}/score", data={"score": "11", "comment": ""}, follow_redirects=True)
    assert "評価は0〜10で選んでください".encode("utf-8") in resp.data

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT COUNT(*) FROM goal_scores WHERE goal_id = %s"), (goal_id,))
    count = cur.fetchone()[0]
    conn.close()
    assert count == 0


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
    cur.execute(db_module.fix("SELECT id FROM goals WHERE employee_id = %s"), (employee_a,))
    goal_id = cur.fetchone()[0]
    conn.close()

    client.get("/logout")
    client.post("/login", data={"password": "general123"})
    client.post("/select-employee", data={"employee_id": str(employee_b)})

    resp = client.post(
        f"/goals/{goal_id}/score",
        data={"score": "5", "comment": "なりすまし"},
        follow_redirects=True,
    )
    assert "不正な操作です".encode("utf-8") in resp.data

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT COUNT(*) FROM goal_scores WHERE goal_id = %s"), (goal_id,))
    count = cur.fetchone()[0]
    conn.close()
    assert count == 0
