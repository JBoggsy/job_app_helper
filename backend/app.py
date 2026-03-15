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
from backend.routes.resume import resume_bp
from backend.routes.job_documents import job_documents_bp


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
    app.register_blueprint(resume_bp)
    app.register_blueprint(job_documents_bp)

    # Initialize telemetry (if enabled)
    _init_telemetry()

    logging.getLogger(__name__).info("App created, log level: %s", app.config.get("LOG_LEVEL", "INFO"))

    return app


def _init_telemetry():
    """Initialize telemetry collector and LiteLLM callback if enabled."""
    import atexit

    from backend.config_manager import get_config_value

    enabled = get_config_value("telemetry.enabled", True)
    if not enabled:
        return

    try:
        from backend.telemetry import init_collector, shutdown_collector
        from backend.telemetry.litellm_hook import register_litellm_callback

        db_path = get_data_dir() / "telemetry.db"
        collector = init_collector(db_path)
        register_litellm_callback()

        # Run compaction on startup
        retention_days = int(get_config_value("telemetry.retention_days", 90))
        collector.compact(retention_days)

        atexit.register(shutdown_collector)
    except Exception:
        logging.getLogger(__name__).debug(
            "Failed to initialize telemetry", exc_info=True,
        )
