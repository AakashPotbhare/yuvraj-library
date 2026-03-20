import os
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from database import get_db, _IS_PG
from routes.auth import login_required

bp = Blueprint("members", __name__, url_prefix="/members")

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_DOC_SIZE = 5 * 1024 * 1024  # 5 MB


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_document(file, member_id):
    """Save document to Supabase Storage (cloud) or local filesystem (PC)."""
    ext = file.filename.rsplit(".", 1)[1].lower()
    safe_name = f"member_{member_id}_{secure_filename(file.filename)}"

    if _IS_PG:
        try:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
            if url and key:
                sb = create_client(url, key)
                file_bytes = file.read()
                sb.storage.from_("member-docs").upload(
                    safe_name, file_bytes,
                    {"content-type": f"image/{ext}" if ext != "pdf" else "application/pdf",
                     "upsert": "true"}
                )
                return f"supabase:{safe_name}"
        except Exception as e:
            import logging
            logging.warning(f"Supabase Storage upload failed: {e}")

    # Local fallback
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "member_docs")
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, safe_name)
    file.seek(0)
    file.save(path)
    return safe_name


@bp.route("")
@login_required
def list_members():
    db = get_db()
    q = request.args.get("q", "").strip()
    if q:
        members = db.execute(
            "SELECT * FROM members WHERE is_active=1 AND (name LIKE ? OR phone LIKE ?) ORDER BY name",
            (f"%{q}%", f"%{q}%")
        ).fetchall()
    else:
        members = db.execute(
            "SELECT * FROM members WHERE is_active=1 ORDER BY name"
        ).fetchall()
    return render_template("members/list.html", members=members, q=q)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_member():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        id_type = request.form.get("id_type", "").strip()
        id_number = request.form.get("id_number", "").strip()
        member_type = request.form.get("member_type", "General").strip()
        error = None
        if not name:
            error = "Name is required."
        elif not phone:
            error = "Phone number is required."
        elif not address:
            error = "Address is required."
        elif not id_number:
            error = "ID number is required."
        if error:
            flash(error, "danger")
            return render_template("members/add.html", form=request.form)

        db = get_db()
        doc_filename = None
        uploaded = request.files.get("doc_file")
        if uploaded and uploaded.filename:
            if not allowed_file(uploaded.filename):
                flash("Only PDF, JPG, PNG files are allowed.", "danger")
                return render_template("members/add.html", form=request.form)
            if len(uploaded.read()) > MAX_DOC_SIZE:
                flash("File too large. Maximum size is 5 MB.", "danger")
                return render_template("members/add.html", form=request.form)
            uploaded.seek(0)
            # Use a placeholder ID (0) for the filename; will be replaced below with real ID
            doc_filename = _save_document(uploaded, "new")

        cursor = db.execute(
            "INSERT INTO members (name, phone, address, id_type, id_number, member_type, doc_filename) VALUES (?,?,?,?,?,?,?)",
            (name, phone, address, id_type, id_number, member_type, doc_filename)
        )
        db.commit()
        member_id = cursor.lastrowid
        db.execute("UPDATE members SET member_code = ? WHERE id = ?",
                   (f"MEM-{member_id:04d}", member_id))
        db.commit()
        flash(f"Member '{name}' added successfully.", "success")
        return redirect(url_for("members.view_member", id=member_id))
    return render_template("members/add.html", form={})


@bp.route("/<int:id>")
@login_required
def view_member(id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id=?", (id,)).fetchone()
    if member is None:
        flash("Member not found.", "danger")
        return redirect(url_for("members.list_members"))
    open_issues = db.execute(
        """SELECT i.*, b.title, b.author, b.rack_location
           FROM issues i JOIN books b ON i.book_id = b.id
           WHERE i.member_id=? AND i.returned_on IS NULL
           ORDER BY i.due_date ASC""",
        (id,)
    ).fetchall()

    doc_filename = member["doc_filename"] or ""
    if doc_filename.startswith("supabase:"):
        key = doc_filename[len("supabase:"):]
        supabase_url = current_app.config.get("SUPABASE_URL", "")
        doc_url = f"{supabase_url}/storage/v1/object/public/member-docs/{key}"
    else:
        doc_url = url_for("static", filename=f"uploads/member_docs/{doc_filename}") if doc_filename else None

    return render_template(
        "members/view.html",
        member=member,
        open_issues=open_issues,
        today=date.today().isoformat(),
        doc_url=doc_url
    )


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_member(id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id=?", (id,)).fetchone()
    if member is None:
        flash("Member not found.", "danger")
        return redirect(url_for("members.list_members"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        id_type = request.form.get("id_type", "").strip()
        id_number = request.form.get("id_number", "").strip()
        member_type = request.form.get("member_type", "General").strip()
        error = None
        if not name:
            error = "Name is required."
        elif not phone:
            error = "Phone is required."
        elif not address:
            error = "Address is required."
        elif not id_number:
            error = "ID number is required."
        if error:
            flash(error, "danger")
            return render_template("members/edit.html", member=member, form=dict(request.form))

        doc_filename = member["doc_filename"]
        uploaded = request.files.get("doc_file")
        if uploaded and uploaded.filename:
            if not allowed_file(uploaded.filename):
                flash("Only PDF, JPG, PNG files are allowed.", "danger")
                return render_template("members/edit.html", member=member, form=dict(request.form))
            if len(uploaded.read()) > MAX_DOC_SIZE:
                flash("File too large. Maximum size is 5 MB.", "danger")
                return render_template("members/edit.html", member=member, form=dict(request.form))
            uploaded.seek(0)
            doc_filename = _save_document(uploaded, id)

        db.execute(
            "UPDATE members SET name=?, phone=?, address=?, id_type=?, id_number=?, member_type=?, doc_filename=? WHERE id=?",
            (name, phone, address, id_type, id_number, member_type, doc_filename, id)
        )
        db.commit()
        flash("Member updated successfully.", "success")
        return redirect(url_for("members.view_member", id=id))
    form_data = dict(member)
    return render_template("members/edit.html", member=member, form=form_data)


@bp.route("/<int:id>/deactivate", methods=["POST"])
@login_required
def deactivate_member(id):
    db = get_db()
    member = db.execute("SELECT id FROM members WHERE id=?", (id,)).fetchone()
    if member is None:
        flash("Member not found.", "danger")
        return redirect(url_for("members.list_members"))
    open_issues = db.execute(
        "SELECT COUNT(*) as cnt FROM issues WHERE member_id=? AND returned_on IS NULL", (id,)
    ).fetchone()["cnt"]
    if open_issues > 0:
        flash(f"Cannot deactivate: member has {open_issues} book(s) currently issued.", "danger")
        return redirect(url_for("members.view_member", id=id))
    db.execute("UPDATE members SET is_active=0 WHERE id=?", (id,))
    db.commit()
    flash("Member deactivated.", "warning")
    return redirect(url_for("members.list_members"))


@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete_member(id):
    db = get_db()
    # Block delete if member has active issues
    active = db.execute(
        "SELECT COUNT(*) AS n FROM issues WHERE member_id=? AND returned_on IS NULL", (id,)
    ).fetchone()["n"]
    if active and int(active) > 0:
        flash(f"Cannot delete: member has {active} book(s) currently issued. Return them first.", "danger")
        return redirect(url_for("members.view_member", id=id))
    db.execute("DELETE FROM issues WHERE member_id=?", (id,))
    db.execute("DELETE FROM members WHERE id=?", (id,))
    db.commit()
    flash("Member deleted permanently.", "success")
    return redirect(url_for("members.list_members"))
