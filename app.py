import os
from datetime import timedelta
from flask import Flask
import config
from database import init_app


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        DATABASE=config.DATABASE_PATH,
        DEFAULT_LOAN_DAYS=config.DEFAULT_LOAN_DAYS,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAIL_HOST=config.MAIL_HOST,
        MAIL_PORT=config.MAIL_PORT,
        MAIL_USERNAME=config.MAIL_USERNAME,
        MAIL_PASSWORD=config.MAIL_PASSWORD,
        SUPABASE_URL=config.SUPABASE_URL,
        SUPABASE_ANON_KEY=config.SUPABASE_ANON_KEY,
        SUPABASE_SERVICE_KEY=config.SUPABASE_SERVICE_KEY,
    )
    if test_config:
        app.config.update(test_config)

    init_app(app)

    with app.app_context():
        from database import init_db
        try:
            init_db()
        except Exception as e:
            import logging
            logging.warning(f"init_db() failed (will retry on first request): {e}")

    # Ensure upload dir exists for local mode
    if not os.environ.get("DATABASE_URL"):
        try:
            upload_dir = os.path.join(app.root_path, "static", "uploads", "member_docs")
            os.makedirs(upload_dir, exist_ok=True)
        except OSError:
            pass

    from routes import dashboard, auth as auth_module, admin as admin_module
    from routes import members, books, issues
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(auth_module.bp)
    app.register_blueprint(admin_module.bp)
    app.register_blueprint(members.bp)
    app.register_blueprint(books.bp)
    app.register_blueprint(issues.bp)

    return app


# Vercel / gunicorn WSGI entry point
app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
