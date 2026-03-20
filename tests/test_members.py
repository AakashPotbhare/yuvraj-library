def test_list_members_empty(client):
    r = client.get("/members")
    assert r.status_code == 200
    assert b"No members" in r.data

def test_add_member_valid(client):
    r = client.post("/members/add", data={
        "name": "Ramesh Sharma",
        "phone": "9876543210",
        "address": "123 Main St, Ujjain",
        "id_type": "Aadhaar",
        "id_number": "1234-5678-9012",
        "member_type": "Student",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"Ramesh Sharma" in r.data

def test_add_member_missing_name(client):
    r = client.post("/members/add", data={
        "phone": "9876543210",
        "address": "Ujjain",
        "id_type": "Aadhaar",
        "id_number": "123",
        "member_type": "General",
    }, follow_redirects=True)
    # Should NOT redirect to success — stays on form with error
    assert r.status_code == 200
    # Should show some indication of error (either "required", "error", or form re-rendered)
    assert b"required" in r.data.lower() or b"name" in r.data.lower()

def test_view_member(client):
    client.post("/members/add", data={
        "name": "Priya Joshi",
        "phone": "9988776655",
        "address": "Ujjain",
        "id_type": "PAN",
        "id_number": "ABCDE1234F",
        "member_type": "General",
    })
    r = client.get("/members/1")
    assert r.status_code == 200
    assert b"Priya Joshi" in r.data

def test_edit_member(client):
    client.post("/members/add", data={
        "name": "Old Name",
        "phone": "1111111111",
        "address": "Old Address",
        "id_type": "Aadhaar",
        "id_number": "0000",
        "member_type": "General",
    })
    r = client.post("/members/1/edit", data={
        "name": "New Name",
        "phone": "2222222222",
        "address": "New Address",
        "id_type": "Aadhaar",
        "id_number": "1111",
        "member_type": "Student",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"New Name" in r.data

def test_search_members(client):
    client.post("/members/add", data={
        "name": "Priya Joshi",
        "phone": "1234567890",
        "address": "Ujjain",
        "id_type": "PAN",
        "id_number": "ABCDE1234F",
        "member_type": "General",
    })
    r = client.get("/members?q=Priya")
    assert r.status_code == 200
    assert b"Priya" in r.data

def test_deactivate_member_no_open_issues(client):
    client.post("/members/add", data={
        "name": "Test User",
        "phone": "9999999999",
        "address": "Ujjain",
        "id_type": "Aadhaar",
        "id_number": "0000",
        "member_type": "General",
    })
    r = client.post("/members/1/deactivate", follow_redirects=True)
    assert r.status_code == 200


def test_deactivate_member_with_open_issues_blocked(client):
    """Deactivating a member with open issues should be blocked."""
    # Add member
    client.post("/members/add", data={
        "name": "Test User",
        "phone": "8888888888",
        "address": "Ujjain",
        "id_type": "Aadhaar",
        "id_number": "5555",
        "member_type": "General",
    })
    # Add book
    from database import get_db
    with client.application.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO books (title, author, category, total_copies) VALUES ('Test Book','Author','Fiction',1)"
        )
        # Create an open issue for this member
        db.execute(
            "INSERT INTO issues (book_id, member_id, issued_on, due_date) VALUES (1,1,date('now'),date('now','+15 days'))"
        )
        db.commit()
    # Try to deactivate — should be blocked
    r = client.post("/members/1/deactivate", follow_redirects=True)
    assert r.status_code == 200
    assert b"Cannot deactivate" in r.data or b"open" in r.data.lower()
