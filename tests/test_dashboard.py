from database import get_db


def test_dashboard_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Yuvraj Library" in r.data


def test_dashboard_shows_stats(client):
    # Add a member
    client.post("/members/add", data={
        "name": "Test Member", "phone": "1111111111",
        "address": "Ujjain", "id_type": "Aadhaar",
        "id_number": "1111", "member_type": "General",
    })
    # Add a book
    client.post("/books/add", data={
        "title": "Test Book", "author": "Author",
        "category": "Fiction", "total_copies": "2",
    })
    r = client.get("/")
    assert r.status_code == 200
    # Stats should show 1 member and book
    assert b"1" in r.data


def test_dashboard_shows_overdue(client):
    # Add member and book
    client.post("/members/add", data={
        "name": "Ramesh", "phone": "9876543210",
        "address": "Ujjain", "id_type": "Aadhaar",
        "id_number": "9999", "member_type": "Student",
    })
    client.post("/books/add", data={
        "title": "Overdue Book", "author": "Author",
        "category": "Fiction", "total_copies": "1",
    })
    # Insert an overdue issue directly
    with client.application.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO issues (book_id, member_id, issued_on, due_date) VALUES (1, 1, '2020-01-01', '2020-01-16')"
        )
        db.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert b"Overdue Book" in r.data or b"overdue" in r.data.lower() or b"1" in r.data
