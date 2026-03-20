from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from database import get_db
from routes.auth import login_required

bp = Blueprint("issues", __name__, url_prefix="/issues")


def get_available_copies(db, book_id):
    """Returns number of available copies for a book."""
    row = db.execute(
        """SELECT b.total_copies - COALESCE(
               (SELECT COUNT(*) FROM issues i WHERE i.book_id=? AND i.returned_on IS NULL), 0
           ) AS available
           FROM books b WHERE b.id=?""",
        (book_id, book_id)
    ).fetchone()
    return row["available"] if row else 0


@bp.route("")
@login_required
def list_issues():
    db = get_db()
    issues = db.execute(
        """SELECT i.*, b.title, b.author, b.rack_location,
                  m.name AS member_name, m.phone
           FROM issues i
           JOIN books b ON i.book_id = b.id
           JOIN members m ON i.member_id = m.id
           WHERE i.returned_on IS NULL
           ORDER BY i.due_date ASC"""
    ).fetchall()
    today = date.today().isoformat()
    return render_template("issues/active.html", issues=issues, today=today)


@bp.route("/overdue")
@login_required
def overdue_list():
    db = get_db()
    today = date.today().isoformat()
    today_date = date.today()
    raw_rows = db.execute(
        """SELECT i.*,
                  b.title, b.author, b.rack_location,
                  m.name AS member_name, m.phone
           FROM issues i
           JOIN books b ON i.book_id = b.id
           JOIN members m ON i.member_id = m.id
           WHERE i.returned_on IS NULL AND i.due_date < ?
           ORDER BY i.due_date ASC""",
        (today,)
    ).fetchall()
    results = []
    for row in raw_rows:
        d = dict(row)
        due = date.fromisoformat(str(d["due_date"])[:10])
        d["days_overdue"] = (today_date - due).days
        results.append(d)
    return render_template("issues/overdue.html", issues=results)


@bp.route("/history")
@login_required
def history():
    db = get_db()
    q = request.args.get("q", "").strip()
    if q:
        issues = db.execute(
            """SELECT i.*, b.title, b.author, m.name AS member_name
               FROM issues i
               JOIN books b ON i.book_id = b.id
               JOIN members m ON i.member_id = m.id
               WHERE b.title LIKE ? OR m.name LIKE ?
               ORDER BY i.created_at DESC LIMIT 200""",
            (f"%{q}%", f"%{q}%")
        ).fetchall()
    else:
        issues = db.execute(
            """SELECT i.*, b.title, b.author, m.name AS member_name
               FROM issues i
               JOIN books b ON i.book_id = b.id
               JOIN members m ON i.member_id = m.id
               ORDER BY i.created_at DESC LIMIT 200"""
        ).fetchall()
    today = date.today().isoformat()
    return render_template("issues/history.html", issues=issues, q=q, today=today)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_issue():
    db = get_db()
    if request.method == "POST":
        try:
            member_id = int(request.form.get("member_id", 0))
            book_id = int(request.form.get("book_id", 0))
        except (ValueError, TypeError):
            flash("Invalid member or book selection.", "danger")
            return redirect(url_for("issues.new_issue"))

        # Validate member
        member = db.execute(
            "SELECT * FROM members WHERE id=? AND is_active=1", (member_id,)
        ).fetchone()
        if not member:
            flash("Member not found or is inactive. Please select an active member.", "danger")
            return redirect(url_for("issues.new_issue"))

        # Validate book
        book = db.execute("SELECT * FROM books WHERE id=? AND is_active=1", (book_id,)).fetchone()
        if not book:
            flash("Book not found.", "danger")
            return redirect(url_for("issues.new_issue"))

        # Check availability
        available = get_available_copies(db, book_id)
        if available <= 0:
            flash(f"No copies available. All {book['total_copies']} copies of '{book['title']}' are currently issued.", "danger")
            return redirect(url_for("issues.new_issue"))

        # Create the issue
        issued_on = date.today().isoformat()
        due_date = (date.today() + timedelta(days=current_app.config["DEFAULT_LOAN_DAYS"])).isoformat()
        db.execute(
            "INSERT INTO issues (book_id, member_id, issued_on, due_date) VALUES (?,?,?,?)",
            (book_id, member_id, issued_on, due_date)
        )
        db.commit()
        flash(f"'{book['title']}' issued to {member['name']}. Due: {due_date}", "success")
        return redirect(url_for("issues.list_issues"))

    # GET — show search + form
    member_q = request.args.get("member_q", "").strip()
    book_q = request.args.get("book_q", "").strip()
    members_found = []
    books_found = []
    if member_q:
        members_found = db.execute(
            "SELECT * FROM members WHERE is_active=1 AND (name LIKE ? OR phone LIKE ?) ORDER BY name LIMIT 10",
            (f"%{member_q}%", f"%{member_q}%")
        ).fetchall()
    if book_q:
        books_found = db.execute(
            """SELECT b.*,
               b.total_copies - COALESCE((SELECT COUNT(*) FROM issues i WHERE i.book_id=b.id AND i.returned_on IS NULL),0) AS available_copies
               FROM books b WHERE b.is_active=1 AND (b.title LIKE ? OR b.author LIKE ?) ORDER BY b.title LIMIT 10""",
            (f"%{book_q}%", f"%{book_q}%")
        ).fetchall()
    selected_member_id = request.args.get("member_id", "")
    selected_book_id = request.args.get("book_id", "")
    return render_template("issues/issue_form.html",
        member_q=member_q, book_q=book_q,
        members_found=members_found, books_found=books_found,
        selected_member_id=selected_member_id,
        selected_book_id=selected_book_id,
        default_loan_days=current_app.config["DEFAULT_LOAN_DAYS"]
    )


@bp.route("/<int:id>/return", methods=["POST"])
@login_required
def return_book(id):
    db = get_db()
    issue = db.execute("SELECT * FROM issues WHERE id=?", (id,)).fetchone()
    if issue is None:
        flash("Issue record not found.", "danger")
        return redirect(url_for("issues.list_issues"))
    if issue["returned_on"] is not None:
        flash("This book has already been returned.", "warning")
        return redirect(url_for("issues.list_issues"))
    db.execute(
        "UPDATE issues SET returned_on=? WHERE id=? AND returned_on IS NULL",
        (date.today().isoformat(), id)
    )
    db.commit()
    flash("Book returned successfully.", "success")
    return redirect(url_for("issues.list_issues"))


@bp.route("/<int:id>/reissue", methods=["POST"])
@login_required
def reissue_book(id):
    db = get_db()
    issue = db.execute("SELECT * FROM issues WHERE id=?", (id,)).fetchone()
    if issue is None:
        flash("Issue record not found.", "danger")
        return redirect(url_for("issues.list_issues"))
    if issue["returned_on"] is not None:
        flash("Cannot reissue a returned book.", "warning")
        return redirect(url_for("issues.list_issues"))
    issue_row = db.execute(
        "SELECT due_date FROM issues WHERE id=? AND returned_on IS NULL", (id,)
    ).fetchone()
    if not issue_row:
        flash("Issue record not found or already returned.", "danger")
        return redirect(url_for("issues.list_issues"))
    due_str = str(issue_row["due_date"])
    current_due = date.fromisoformat(due_str[:10])
    new_due = (current_due + timedelta(days=current_app.config["DEFAULT_LOAN_DAYS"])).isoformat()
    db.execute(
        "UPDATE issues SET due_date=?, reissue_count=reissue_count+1 WHERE id=? AND returned_on IS NULL",
        (new_due, id)
    )
    db.commit()
    flash(f"Book reissued. New due date: {new_due}", "success")
    return redirect(url_for("issues.list_issues"))
