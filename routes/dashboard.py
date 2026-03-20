from flask import Blueprint, render_template
from database import get_db

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    db = get_db()

    total_copies = db.execute(
        "SELECT COALESCE(SUM(total_copies), 0) AS n FROM books WHERE is_active=1"
    ).fetchone()["n"]

    total_members = db.execute(
        "SELECT COUNT(*) AS n FROM members WHERE is_active=1"
    ).fetchone()["n"]

    currently_issued = db.execute(
        "SELECT COUNT(*) AS n FROM issues WHERE returned_on IS NULL"
    ).fetchone()["n"]

    overdue_count = db.execute(
        "SELECT COUNT(*) AS n FROM issues WHERE returned_on IS NULL AND due_date < date('now')"
    ).fetchone()["n"]

    overdue_items = db.execute(
        """SELECT i.*,
                  b.title, b.author,
                  m.name AS member_name, m.phone,
                  CAST(julianday('now') - julianday(i.due_date) AS INTEGER) AS days_overdue
           FROM issues i
           JOIN books b ON i.book_id = b.id
           JOIN members m ON i.member_id = m.id
           WHERE i.returned_on IS NULL AND i.due_date < date('now')
           ORDER BY i.due_date ASC
           LIMIT 5"""
    ).fetchall()

    return render_template("dashboard.html",
        total_copies=total_copies,
        total_members=total_members,
        currently_issued=currently_issued,
        overdue_count=overdue_count,
        overdue_items=overdue_items
    )
