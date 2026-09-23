def test_login_page_loads(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_login_with_admin_password_redirects_to_admin_menu(client):
    resp = client.post("/login", data={"password": "admin123"}, follow_redirects=True)
    assert "店長メニュー".encode("utf-8") in resp.data


def test_login_with_general_password_redirects_to_select_employee(client):
    resp = client.post("/login", data={"password": "general123"}, follow_redirects=True)
    assert "お名前を選択してください".encode("utf-8") in resp.data


def test_login_with_wrong_password_shows_error(client):
    resp = client.post("/login", data={"password": "wrong"}, follow_redirects=True)
    assert "パスワードが違います".encode("utf-8") in resp.data


def test_admin_menu_requires_login(client):
    resp = client.get("/admin", follow_redirects=True)
    assert "パスワードを入力".encode("utf-8") in resp.data or "ログイン".encode("utf-8") in resp.data


def test_employee_menu_requires_employee_selected(client):
    client.post("/login", data={"password": "general123"})
    resp = client.get("/employee", follow_redirects=True)
    assert "お名前を選択してください".encode("utf-8") in resp.data
