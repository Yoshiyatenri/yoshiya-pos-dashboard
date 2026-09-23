import db as db_module


def _login_admin(client):
    client.post("/login", data={"password": "admin123"})


def _add_employee_and_login(client, name="提案太郎"):
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


def test_named_proposal_is_linked_to_employee(client):
    employee_id = _add_employee_and_login(client)
    client.post("/proposals", data={"content": "レジ横の陳列を変えたい"}, follow_redirects=True)

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT employee_id, content FROM proposals WHERE content = %s"), ("レジ横の陳列を変えたい",))
    row = cur.fetchone()
    conn.close()
    assert row[0] == employee_id


def test_anonymous_proposal_does_not_store_employee_id(client):
    _add_employee_and_login(client)
    client.post(
        "/proposals",
        data={"content": "匿名の意見", "is_anonymous": "on"},
        follow_redirects=True,
    )

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT employee_id FROM proposals WHERE content = %s"), ("匿名の意見",))
    row = cur.fetchone()
    conn.close()
    assert row[0] is None


def test_admin_can_see_and_update_proposal_status(client):
    employee_id = _add_employee_and_login(client)
    client.post("/proposals", data={"content": "休憩室を改善したい"})

    client.get("/logout")
    _login_admin(client)
    resp = client.get("/admin/proposals")
    assert "休憩室を改善したい".encode("utf-8") in resp.data

    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM proposals WHERE content = %s"), ("休憩室を改善したい",))
    proposal_id = cur.fetchone()[0]
    conn.close()

    client.post(f"/admin/proposals/{proposal_id}/status", data={"status": "対応中"}, follow_redirects=True)
    resp = client.get("/admin/proposals")
    assert "対応中".encode("utf-8") in resp.data
