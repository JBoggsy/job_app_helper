import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate, upgrade, stamp
from werkzeug.exceptions import HTTPException

from backend.config import Config
from backend.data_dir import get_data_dir
from backend.database import db
from backend.routes.jobs import jobs_bp
from backend.routes.chat import chat_bp
from backend.routes.profile import profile_bp
from backend.routes.config import config_bp
from backend.routes.resume import resume_bp
from backend.routes.job_documents import job_documents_bp

migrate = Migrate(render_as_batch=True)


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


def _register_error_handlers(app):
    """Register global JSON error handlers so the API never returns HTML."""
    _logger = logging.getLogger(__name__)

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": e.description or "Bad request"}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(Exception)
    def handle_exception(e):
        # Pass through HTTP exceptions with their original status code
        if isinstance(e, HTTPException):
            return jsonify({"error": e.description or e.name}), e.code
        _logger.exception("Unhandled exception")
        return jsonify({"error": "Internal server error"}), 500


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    _setup_logging(app.config.get("LOG_LEVEL", "INFO"))

    CORS(app)
    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        _apply_migrations(app)

    _register_error_handlers(app)

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


def _apply_migrations(app):
    """Apply database migrations on startup.

    Handles three scenarios:
    1. Fresh database (no tables) — run all migrations from scratch.
    2. Pre-migration database (tables exist, no alembic_version tracking) —
       stamp at the initial baseline, then upgrade to apply newer migrations.
    3. Normal database (alembic_version exists and populated) — just upgrade().

    Falls back to db.create_all() if the migrations directory doesn't exist
    (development convenience).
    """
    _logger = logging.getLogger(__name__)
    migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")

    if not os.path.isdir(migrations_dir):
        _logger.warning("Migrations directory not found — falling back to db.create_all()")
        db.create_all()
        return

    inspector = db.inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    has_app_tables = bool(existing_tables - {"alembic_version"})

    # Check if Alembic is already tracking this database
    has_version = False
    if "alembic_version" in existing_tables:
        row = db.session.execute(db.text("SELECT version_num FROM alembic_version")).first()
        has_version = row is not None

    if has_app_tables and not has_version:
        # Pre-migration database: tables exist but no migration tracking.
        # Stamp at the initial baseline so only newer migrations run.
        _logger.info("Pre-migration database detected — stamping baseline")
        stamp(directory=migrations_dir, revision="2d18089fe7f9")

    upgrade(directory=migrations_dir)
    _logger.info("Database migrations applied successfully")


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
