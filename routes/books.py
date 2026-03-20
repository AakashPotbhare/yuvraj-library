from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db

bp = Blueprint("books", __name__, url_prefix="/books")

CATEGORIES = [
    "Fiction", "Non-Fiction", "Science", "Mathematics", "History",
    "Geography", "Religion & Spirituality", "Biography",
    "Education / Textbook", "Children", "Law", "Medicine",
    "Literature / Poetry", "Other"
]

@bp.route("")
def list_books():
    db = get_db()
    q = request.args.get("q", "").strip()
    if q:
        books = db.execute(
            """SELECT b.*,
               b.total_copies - COALESCE((
                   SELECT COUNT(*) FROM issues i
                   WHERE i.book_id = b.id AND i.returned_on IS NULL
               ), 0) AS available_copies
               FROM books b
               WHERE b.is_active=1 AND (b.title LIKE ? OR b.author LIKE ? OR b.category LIKE ?)
               ORDER BY b.title""",
            (f"%{q}%", f"%{q}%", f"%{q}%")
        ).fetchall()
    else:
        books = db.execute(
            """SELECT b.*,
               b.total_copies - COALESCE((
                   SELECT COUNT(*) FROM issues i
                   WHERE i.book_id = b.id AND i.returned_on IS NULL
               ), 0) AS available_copies
               FROM books b
               WHERE b.is_active=1 ORDER BY b.title"""
        ).fetchall()
    return render_template("books/list.html", books=books, q=q)

@bp.route("/add", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        try:
            total_copies = int(request.form.get("total_copies", 1))
            if total_copies < 1:
                total_copies = 1
        except (ValueError, TypeError):
            total_copies = 1
        isbn = request.form.get("isbn", "").strip()
        publisher = request.form.get("publisher", "").strip()
        year = request.form.get("year", "").strip()
        rack_location = request.form.get("rack_location", "").strip()
        error = None
        if not title:
            error = "Book title is required."
        elif not author:
            error = "Author is required."
        elif not category:
            error = "Category is required."
        elif category not in CATEGORIES:
            error = "Please select a valid category."
        if error:
            flash(error, "danger")
            return render_template("books/add.html", form=dict(request.form), categories=CATEGORIES)
        db = get_db()
        cursor = db.execute(
            "INSERT INTO books (title, author, isbn, publisher, year, category, rack_location, total_copies) VALUES (?,?,?,?,?,?,?,?)",
            (title, author, isbn or None, publisher or None, int(year) if year else None, category, rack_location or None, total_copies)
        )
        db.commit()
        book_id = cursor.lastrowid
        flash(f"Book '{title}' added successfully.", "success")
        return redirect(url_for("books.view_book", id=book_id))
    return render_template("books/add.html", form={}, categories=CATEGORIES)

@bp.route("/<int:id>")
def view_book(id):
    db = get_db()
    book = db.execute(
        """SELECT b.*,
           b.total_copies - COALESCE((
               SELECT COUNT(*) FROM issues i
               WHERE i.book_id = b.id AND i.returned_on IS NULL
           ), 0) AS available_copies
           FROM books b WHERE b.id=?""",
        (id,)
    ).fetchone()
    if book is None:
        flash("Book not found.", "danger")
        return redirect(url_for("books.list_books"))
    current_holders = db.execute(
        """SELECT i.*, m.name AS member_name, m.phone
           FROM issues i JOIN members m ON i.member_id = m.id
           WHERE i.book_id=? AND i.returned_on IS NULL
           ORDER BY i.due_date ASC""",
        (id,)
    ).fetchall()
    return render_template("books/view.html", book=book, current_holders=current_holders, today=date.today().isoformat())

@bp.route("/<int:id>/edit", methods=["GET", "POST"])
def edit_book(id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id=?", (id,)).fetchone()
    if book is None:
        flash("Book not found.", "danger")
        return redirect(url_for("books.list_books"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        try:
            total_copies = int(request.form.get("total_copies", 1))
            if total_copies < 1:
                total_copies = 1
        except (ValueError, TypeError):
            total_copies = 1
        isbn = request.form.get("isbn", "").strip()
        publisher = request.form.get("publisher", "").strip()
        year = request.form.get("year", "").strip()
        rack_location = request.form.get("rack_location", "").strip()
        error = None
        if not title:
            error = "Book title is required."
        elif not author:
            error = "Author is required."
        elif not category:
            error = "Category is required."
        elif category not in CATEGORIES:
            error = "Please select a valid category."
        if error:
            flash(error, "danger")
            form_data = dict(request.form)
            return render_template("books/edit.html", book=book, form=form_data, categories=CATEGORIES)
        db.execute(
            "UPDATE books SET title=?, author=?, isbn=?, publisher=?, year=?, category=?, rack_location=?, total_copies=? WHERE id=?",
            (title, author, isbn or None, publisher or None, int(year) if year else None, category, rack_location or None, total_copies, id)
        )
        db.commit()
        flash("Book updated.", "success")
        return redirect(url_for("books.view_book", id=id))
    form_data = {k: ('' if v is None else v) for k, v in dict(book).items()}
    return render_template("books/edit.html", book=book, form=form_data, categories=CATEGORIES)
