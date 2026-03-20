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

    from routes import members
    app.register_blueprint(members.bp)

    from routes import books
    app.register_blueprint(books.bp)

    from routes import issues
    app.register_blueprint(issues.bp)

    return app


if __name__ == "__main__":
    from database import init_db
    app = create_app()
    with app.app_context():
        init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
