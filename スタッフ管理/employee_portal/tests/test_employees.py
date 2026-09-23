def _login_admin(client):
    client.post("/login", data={"password": "admin123"})


def test_add_employee_appears_in_list(client):
    _login_admin(client)
    client.post("/admin/employees/add", data={"name": "山田花子"}, follow_redirects=True)
    resp = client.get("/admin/employees/")
    assert "山田花子".encode("utf-8") in resp.data


def test_add_employee_without_name_shows_error(client):
    _login_admin(client)
    resp = client.post("/admin/employees/add", data={"name": ""}, follow_redirects=True)
    assert "名前を入力してください".encode("utf-8") in resp.data


def test_deactivate_employee_hides_from_active_list(client):
    _login_admin(client)
    client.post("/admin/employees/add", data={"name": "退職予定者"})

    import db as db_module
    conn = db_module.get_conn()
    cur = conn.cursor()
    cur.execute(db_module.fix("SELECT id FROM employees WHERE name = %s"), ("退職予定者",))
    employee_id = cur.fetchone()[0]
    conn.close()

    client.post(f"/admin/employees/{employee_id}/deactivate", follow_redirects=True)
    resp = client.get("/admin/employees/")
    assert "退職".encode("utf-8") in resp.data


def test_employees_page_requires_admin(client):
    resp = client.get("/admin/employees/", follow_redirects=True)
    assert "パスワードを入力".encode("utf-8") in resp.data
