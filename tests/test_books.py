def test_list_books_empty(client):
    r = client.get("/books")
    assert r.status_code == 200
    assert b"No books" in r.data

def test_add_book_valid(client):
    r = client.post("/books/add", data={
        "title": "Godan",
        "author": "Munshi Premchand",
        "category": "Literature / Poetry",
        "total_copies": "2",
        "rack_location": "A1",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"Godan" in r.data

def test_add_book_missing_title(client):
    r = client.post("/books/add", data={
        "author": "Some Author",
        "category": "Fiction",
        "total_copies": "1",
    }, follow_redirects=True)
    assert r.status_code == 200
    # Should re-render form with error, not redirect to book view

def test_search_books_by_author(client):
    client.post("/books/add", data={
        "title": "Godan",
        "author": "Premchand",
        "category": "Fiction",
        "total_copies": "1",
    })
    r = client.get("/books?q=Premchand")
    assert r.status_code == 200
    assert b"Godan" in r.data

def test_search_books_by_title(client):
    client.post("/books/add", data={
        "title": "Ramcharitmanas",
        "author": "Tulsidas",
        "category": "Religion & Spirituality",
        "total_copies": "3",
    })
    r = client.get("/books?q=Ramchari")
    assert r.status_code == 200
    assert b"Ramcharitmanas" in r.data

def test_view_book_shows_copies(client):
    client.post("/books/add", data={
        "title": "Test Book",
        "author": "Test Author",
        "category": "Education / Textbook",
        "total_copies": "3",
    })
    r = client.get("/books/1")
    assert r.status_code == 200
    assert b"Test Book" in r.data
    assert b"3" in r.data  # total copies shown

def test_edit_book(client):
    client.post("/books/add", data={
        "title": "Old Title",
        "author": "Author",
        "category": "Fiction",
        "total_copies": "1",
    })
    r = client.post("/books/1/edit", data={
        "title": "New Title",
        "author": "New Author",
        "category": "Science",
        "total_copies": "2",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"New Title" in r.data
