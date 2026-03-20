from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from database import get_db
from routes.auth import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/users")
@admin_required
def users():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return render_template("admin/users.html", users=users,
                           current_user_id=session.get("user_id"))


@bp.route("/users/add", methods=["GET", "POST"])
@admin_required
def add_user():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "staff")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
        elif role not in ("admin", "staff"):
            flash("Invalid role.", "danger")
        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
                    (username, email, generate_password_hash(password), role)
                )
                db.commit()
                flash(f"User '{username}' created.", "success")
                return redirect(url_for("admin.users"))
            except Exception:
                flash("Username or email already exists.", "danger")

    return render_template("admin/add_user.html")


@bp.route("/users/<int:id>/toggle", methods=["POST"])
@admin_required
def toggle_user(id):
    if id == session.get("user_id"):
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("admin.users"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (id,)).fetchone()
    if user:
        new_state = 0 if user["is_active"] else 1
        db.execute("UPDATE users SET is_active=? WHERE id=?", (new_state, id))
        db.commit()
        state_str = "activated" if new_state else "deactivated"
        flash(f"User '{user['username']}' {state_str}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:id>/reset-password", methods=["POST"])
@admin_required
def reset_user_password(id):
    new_password = request.form.get("new_password", "").strip()
    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "danger")
        return redirect(url_for("admin.users"))
    db = get_db()
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (generate_password_hash(new_password), id))
    db.commit()
    flash("Password updated.", "success")
    return redirect(url_for("admin.users"))
