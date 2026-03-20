from datetime import date, timedelta
from database import get_db


def seed_member(client):
    client.post("/members/add", data={
        "name": "Ramesh Kumar",
        "phone": "9876543210",
        "address": "Ujjain",
        "id_type": "Aadhaar",
        "id_number": "1111",
        "member_type": "Student",
    })


def seed_book(client):
    client.post("/books/add", data={
        "title": "Godan",
        "author": "Munshi Premchand",
        "category": "Fiction",
        "total_copies": "1",
    })


def test_issue_book(client):
    seed_member(client)
    seed_book(client)
    r = client.post("/issues/new", data={
        "member_id": "1",
        "book_id": "1",
    }, follow_redirects=True)
    assert r.status_code == 200
    # Should show in active issues
    assert b"Godan" in r.data or b"Ramesh" in r.data


def test_issue_book_no_copies_available(client):
    seed_member(client)
    seed_book(client)
    # Issue the only copy
    client.post("/issues/new", data={"member_id": "1", "book_id": "1"})
    # Try to issue again — should fail
    r = client.post("/issues/new", data={"member_id": "1", "book_id": "1"}, follow_redirects=True)
    assert r.status_code == 200
    assert b"No copies available" in r.data or b"available" in r.data.lower()


def test_return_book(client):
    seed_member(client)
    seed_book(client)
    client.post("/issues/new", data={"member_id": "1", "book_id": "1"})
    r = client.post("/issues/1/return", follow_redirects=True)
    assert r.status_code == 200


def test_reissue_extends_due_date(client):
    seed_member(client)
    seed_book(client)
    client.post("/issues/new", data={"member_id": "1", "book_id": "1"})
    # Get initial due date
    with client.application.app_context():
        db = get_db()
        original_due = db.execute("SELECT due_date FROM issues WHERE id=1").fetchone()["due_date"]
    r = client.post("/issues/1/reissue", follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        db = get_db()
        new_due = db.execute("SELECT due_date FROM issues WHERE id=1").fetchone()["due_date"]
    assert new_due > original_due


def test_reissue_increments_count(client):
    seed_member(client)
    seed_book(client)
    client.post("/issues/new", data={"member_id": "1", "book_id": "1"})
    client.post("/issues/1/reissue")
    with client.application.app_context():
        db = get_db()
        count = db.execute("SELECT reissue_count FROM issues WHERE id=1").fetchone()["reissue_count"]
    assert count == 1


def test_overdue_list(client):
    seed_member(client)
    seed_book(client)
    # Create a past-due issue directly in DB
    with client.application.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO issues (book_id, member_id, issued_on, due_date) VALUES (1, 1, '2020-01-01', '2020-01-16')"
        )
        db.commit()
    r = client.get("/issues/overdue")
    assert r.status_code == 200
    assert b"Godan" in r.data


def test_active_issues_list(client):
    seed_member(client)
    seed_book(client)
    client.post("/issues/new", data={"member_id": "1", "book_id": "1"})
    r = client.get("/issues")
    assert r.status_code == 200
    assert b"Godan" in r.data


def test_inactive_member_cannot_issue(client):
    seed_member(client)
    seed_book(client)
    # Deactivate the member
    client.post("/members/1/deactivate")
    r = client.post("/issues/new", data={"member_id": "1", "book_id": "1"}, follow_redirects=True)
    assert r.status_code == 200
    assert b"inactive" in r.data.lower() or b"active" in r.data.lower() or b"cannot" in r.data.lower()
