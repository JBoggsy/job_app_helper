import logging
import os

from flask import Flask
from flask_cors import CORS

from backend.config import Config
from backend.data_dir import get_data_dir
from backend.database import db
from backend.routes.jobs import jobs_bp
from backend.routes.chat import chat_bp
from backend.routes.profile import profile_bp
from backend.routes.config import config_bp


def _setup_logging(log_level_name):
    """Configure root logger with console and file handlers."""
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)
    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    root.setLevel(log_level)

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # File handler
    log_dir = str(get_data_dir() / "logs")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(log_dir, "app.log"))
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Quiet noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    _setup_logging(app.config.get("LOG_LEVEL", "INFO"))

    CORS(app)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(jobs_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(config_bp)

    logging.getLogger(__name__).info("App created, log level: %s", app.config.get("LOG_LEVEL", "INFO"))

    return app
