import pytest
import tempfile
import os
from app import create_app
from database import init_db

@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    app = create_app({"TESTING": True, "DATABASE": db_path})
    with app.app_context():
        init_db()
    yield app
    os.unlink(db_path)

@pytest.fixture
def client(app):
    return app.test_client()
