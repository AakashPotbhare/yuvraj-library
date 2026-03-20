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
    )
    if test_config:
        app.config.update(test_config)
    init_app(app)

    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    app.config["MAIL_HOST"] = config.MAIL_HOST
    app.config["MAIL_PORT"] = config.MAIL_PORT
    app.config["MAIL_USERNAME"] = config.MAIL_USERNAME
    app.config["MAIL_PASSWORD"] = config.MAIL_PASSWORD

    upload_dir = os.path.join(app.root_path, "static", "uploads", "member_docs")
    os.makedirs(upload_dir, exist_ok=True)

    from routes import dashboard
    app.register_blueprint(dashboard.bp)

    from routes import members
    app.register_blueprint(members.bp)

    from routes import books
    app.register_blueprint(books.bp)

    from routes import issues
    app.register_blueprint(issues.bp)

    from routes import auth as auth_module
    app.register_blueprint(auth_module.bp)

    from routes import admin as admin_module
    app.register_blueprint(admin_module.bp)

    return app


if __name__ == "__main__":
    from database import init_db
    app = create_app()
    with app.app_context():
        init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
