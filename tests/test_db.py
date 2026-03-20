def test_init_db_creates_tables(app):
    with app.app_context():
        from database import get_db
        db = get_db()
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = [t["name"] for t in tables]
        assert "members" in names
        assert "books" in names
        assert "issues" in names
