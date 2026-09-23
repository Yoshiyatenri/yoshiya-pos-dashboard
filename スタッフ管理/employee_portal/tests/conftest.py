import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db as db_module  # noqa: E402
from app import create_app  # noqa: E402


@pytest.fixture
def app(tmp_path):
    db_module.set_config_override({
        "db_url": "",
        "db_path_sqlite": str(tmp_path / "test.db"),
        "admin_password": "admin123",
        "general_password": "general123",
        "secret_key": "test-secret",
    })
    application = create_app()
    application.testing = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()
