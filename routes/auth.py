import smtplib
import random
import string
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, current_app)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

bp = Blueprint("auth", __name__)


# ── helpers ──────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("user_role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated


def _send_reset_email(to_email, otp, username):
    """Send OTP via Gmail SMTP. Returns True on success."""
    cfg = current_app.config
    mail_user = cfg.get("MAIL_USERNAME")
    mail_pass = cfg.get("MAIL_PASSWORD")
    mail_host = cfg.get("MAIL_HOST", "smtp.gmail.com")
    mail_port = cfg.get("MAIL_PORT", 587)

    if not mail_user or not mail_pass:
        return False  # email not configured

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Yuvraj Library — Password Reset OTP"
    msg["From"] = f"Yuvraj Library <{mail_user}>"
    msg["To"] = to_email

    body = f"""Hello {username},

Your password reset OTP for Yuvraj Library is:

    {otp}

This code is valid for 15 minutes.

If you did not request this, please ignore this email.

— Yuvraj Library, Chhatri Chowk, Ujjain
"""
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(mail_host, mail_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(mail_user, mail_pass)
            server.sendmail(mail_user, to_email, msg.as_string())
        return True
    except Exception as e:
        current_app.logger.error(f"Mail error: {e}")
        return False


def _generate_otp():
    return "".join(random.choices(string.digits, k=6))


# ── first-run setup ───────────────────────────────────────

@bp.route("/setup", methods=["GET", "POST"])
def setup():
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            db.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
                (username, email, generate_password_hash(password), "admin")
            )
            db.commit()
            flash("Admin account created. Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/setup.html")


# ── login / logout ────────────────────────────────────────

@bp.route("/login", methods=["GET", "POST"])
def login():
    db = get_db()
    # Redirect to setup if no users exist
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        return redirect(url_for("auth.setup"))
    # Already logged in
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND is_active=1", (username,)
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_role"] = user["role"]
            session.permanent = True
            next_url = request.args.get("next") or url_for("dashboard.index")
            return redirect(next_url)
        else:
            flash("Incorrect username or password.", "danger")

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


# ── forgot / reset password ───────────────────────────────

@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email=? AND is_active=1", (email,)
        ).fetchone()

        otp = _generate_otp()
        expiry = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

        if user:
            db.execute(
                "UPDATE users SET reset_token=?, reset_token_expiry=? WHERE id=?",
                (otp, expiry, user["id"])
            )
            db.commit()
            sent = _send_reset_email(email, otp, user["username"])
            session["reset_email"] = email
            if sent:
                flash("A 6-digit OTP has been sent to your email.", "success")
            else:
                # Email not configured — show OTP in flash for local/offline use
                flash(
                    f"Email not configured. Your OTP is: <strong>{otp}</strong> "
                    f"(valid 15 min). "
                    f"<a href='/reset-email-setup'>Configure email →</a>",
                    "warning"
                )
        else:
            # Don't reveal if email exists — same message
            flash("If that email is registered, an OTP has been sent.", "info")

        return redirect(url_for("auth.verify_otp"))

    return render_template("auth/forgot_password.html")


@bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        db = get_db()

        user = db.execute(
            "SELECT * FROM users WHERE email=? AND reset_token=?", (email, otp)
        ).fetchone()

        if not user:
            flash("Invalid OTP.", "danger")
        elif user["reset_token_expiry"] < datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
            flash("OTP has expired. Please request a new one.", "danger")
            return redirect(url_for("auth.forgot_password"))
        elif new_password != confirm:
            flash("Passwords do not match.", "danger")
        elif len(new_password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            db.execute(
                "UPDATE users SET password_hash=?, reset_token=NULL, reset_token_expiry=NULL WHERE id=?",
                (generate_password_hash(new_password), user["id"])
            )
            db.commit()
            session.pop("reset_email", None)
            flash("Password updated successfully. Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/verify_otp.html", email=email)
