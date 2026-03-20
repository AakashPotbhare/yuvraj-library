from datetime import date
from flask import Blueprint, render_template
from database import get_db
from routes.auth import login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    db = get_db()
    today = date.today().isoformat()
    today_date = date.today()

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
        "SELECT COUNT(*) AS n FROM issues WHERE returned_on IS NULL AND due_date < ?",
        (today,)
    ).fetchone()["n"]

    raw_overdue = db.execute(
        """SELECT i.*,
                  b.title, b.author,
                  m.name AS member_name, m.phone
           FROM issues i
           JOIN books b ON i.book_id = b.id
           JOIN members m ON i.member_id = m.id
           WHERE i.returned_on IS NULL AND i.due_date < ?
           ORDER BY i.due_date ASC
           LIMIT 5""",
        (today,)
    ).fetchall()

    overdue_items = []
    for row in raw_overdue:
        d = dict(row)
        due = date.fromisoformat(str(d["due_date"])[:10])
        d["days_overdue"] = (today_date - due).days
        overdue_items.append(d)

    return render_template("dashboard.html",
        total_copies=total_copies,
        total_members=total_members,
        currently_issued=currently_issued,
        overdue_count=overdue_count,
        overdue_items=overdue_items
    )
