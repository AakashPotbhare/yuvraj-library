import pytest
import tempfile
import os
from app import create_app
from database import init_db, get_db

@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    app = create_app({"TESTING": True, "DATABASE": db_path})
    with app.app_context():
        init_db()
        db = get_db()
        from werkzeug.security import generate_password_hash
        db.execute(
            "INSERT OR IGNORE INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
            ("testadmin", "test@example.com", generate_password_hash("testpass"), "admin")
        )
        db.commit()
    yield app
    os.unlink(db_path)

@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"username": "testadmin", "password": "testpass"})
    return c
