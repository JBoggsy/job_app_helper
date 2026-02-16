from flask import Flask
from flask_cors import CORS

from backend.config import Config
from backend.database import db
from backend.routes.jobs import jobs_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(jobs_bp)

    return app
