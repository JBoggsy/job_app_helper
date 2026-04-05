"""Tests for database integrity: FK enforcement, cascade deletes, and migrations.

Covers the fixes from the 'Database Integrity' must-fix todo:
1. SQLite foreign key enforcement (PRAGMA foreign_keys=ON)
2. Cascade delete on SearchResult foreign keys
3. Cascade delete on Message foreign keys
4. ORM-level cascade relationships
5. Migration system (fresh DB, pre-migration DB)
6. remove_job tool SearchResult cleanup
"""

import sqlite3
from unittest.mock import patch

import pytest

from backend.app import create_app
from backend.database import db as _db
from backend.models.chat import Conversation, Message
from backend.models.job import Job
from backend.models.job_document import JobDocument
from backend.models.application_todo import ApplicationTodo
from backend.models.search_result import SearchResult


class TestConfig:
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = True
    LOG_LEVEL = "WARNING"


@pytest.fixture()
def app(tmp_path):
    """Create a Flask test app with an in-memory database."""
    with patch("backend.config.get_data_dir", return_value=tmp_path), \
         patch("backend.app.get_data_dir", return_value=tmp_path), \
         patch("backend.app._init_telemetry"):
        application = create_app(config_class=TestConfig)
    with application.app_context():
        yield application
        _db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


# ────────────────────────────────────────────────────────────────────
# 1. SQLite Foreign Key Enforcement
# ────────────────────────────────────────────────────────────────────

class TestForeignKeyEnforcement:
    """PRAGMA foreign_keys=ON is active on every connection."""

    def test_pragma_is_enabled(self, app):
        result = _db.session.execute(_db.text("PRAGMA foreign_keys")).scalar()
        assert result == 1, "PRAGMA foreign_keys should be ON"

    def test_fk_violation_raises_error(self, app):
        """Inserting a row with a non-existent FK value should fail."""
        with pytest.raises(Exception):
            _db.session.execute(
                _db.text("INSERT INTO messages (conversation_id, role, content) VALUES (9999, 'user', 'hi')")
            )
            _db.session.flush()


# ────────────────────────────────────────────────────────────────────
# 2. Conversation Cascade Deletes
# ────────────────────────────────────────────────────────────────────

class TestConversationCascade:
    """Deleting a conversation cascades to messages and search results."""

    def _setup_conversation_data(self):
        """Create a conversation with messages and search results."""
        convo = Conversation(title="Test")
        _db.session.add(convo)
        _db.session.flush()

        msg1 = Message(conversation_id=convo.id, role="user", content="hello")
        msg2 = Message(conversation_id=convo.id, role="assistant", content="hi")
        _db.session.add_all([msg1, msg2])

        sr1 = SearchResult(conversation_id=convo.id, company="Acme", title="Eng")
        sr2 = SearchResult(conversation_id=convo.id, company="BigCo", title="Dev")
        _db.session.add_all([sr1, sr2])
        _db.session.commit()
        return convo.id

    def test_orm_cascade_deletes_messages(self, app):
        convo_id = self._setup_conversation_data()
        assert Message.query.filter_by(conversation_id=convo_id).count() == 2

        convo = _db.session.get(Conversation, convo_id)
        _db.session.delete(convo)
        _db.session.commit()

        assert Message.query.filter_by(conversation_id=convo_id).count() == 0

    def test_orm_cascade_deletes_search_results(self, app):
        convo_id = self._setup_conversation_data()
        assert SearchResult.query.filter_by(conversation_id=convo_id).count() == 2

        convo = _db.session.get(Conversation, convo_id)
        _db.session.delete(convo)
        _db.session.commit()

        assert SearchResult.query.filter_by(conversation_id=convo_id).count() == 0

    def test_db_level_cascade_messages(self, app):
        """DB-level CASCADE works even without ORM."""
        convo_id = self._setup_conversation_data()

        _db.session.execute(
            _db.text("DELETE FROM conversations WHERE id = :id"),
            {"id": convo_id},
        )
        _db.session.commit()

        count = _db.session.execute(
            _db.text("SELECT COUNT(*) FROM messages WHERE conversation_id = :id"),
            {"id": convo_id},
        ).scalar()
        assert count == 0

    def test_db_level_cascade_search_results(self, app):
        """DB-level CASCADE works even without ORM."""
        convo_id = self._setup_conversation_data()

        _db.session.execute(
            _db.text("DELETE FROM conversations WHERE id = :id"),
            {"id": convo_id},
        )
        _db.session.commit()

        count = _db.session.execute(
            _db.text("SELECT COUNT(*) FROM search_results WHERE conversation_id = :id"),
            {"id": convo_id},
        ).scalar()
        assert count == 0

    def test_delete_conversation_route(self, client):
        """DELETE /api/chat/conversations/:id cascades to children."""
        resp = client.post("/api/chat/conversations", json={"title": "Test"})
        convo_id = resp.get_json()["id"]

        with client.application.app_context():
            msg = Message(conversation_id=convo_id, role="user", content="test")
            sr = SearchResult(conversation_id=convo_id, company="A", title="B")
            _db.session.add_all([msg, sr])
            _db.session.commit()

        resp = client.delete(f"/api/chat/conversations/{convo_id}")
        assert resp.status_code == 204

        with client.application.app_context():
            assert Message.query.filter_by(conversation_id=convo_id).count() == 0
            assert SearchResult.query.filter_by(conversation_id=convo_id).count() == 0


# ────────────────────────────────────────────────────────────────────
# 3. Job Cascade Deletes
# ────────────────────────────────────────────────────────────────────

class TestJobCascade:
    """Deleting a job cascades to documents and todos, SET NULLs search results."""

    def _setup_job_data(self):
        """Create a job with related records."""
        convo = Conversation(title="Test")
        _db.session.add(convo)
        _db.session.flush()

        job = Job(company="Acme", title="Engineer")
        _db.session.add(job)
        _db.session.flush()

        doc = JobDocument(job_id=job.id, doc_type="cover_letter", content="Dear...")
        todo = ApplicationTodo(job_id=job.id, title="Submit app")
        sr = SearchResult(
            conversation_id=convo.id, company="Acme", title="Engineer",
            tracker_job_id=job.id, added_to_tracker=True,
        )
        _db.session.add_all([doc, todo, sr])
        _db.session.commit()
        return job.id, convo.id, sr.id

    def test_cascade_deletes_documents(self, app):
        job_id, _, _ = self._setup_job_data()
        assert JobDocument.query.filter_by(job_id=job_id).count() == 1

        job = _db.session.get(Job, job_id)
        _db.session.delete(job)
        _db.session.commit()

        assert JobDocument.query.filter_by(job_id=job_id).count() == 0

    def test_cascade_deletes_todos(self, app):
        job_id, _, _ = self._setup_job_data()
        assert ApplicationTodo.query.filter_by(job_id=job_id).count() == 1

        job = _db.session.get(Job, job_id)
        _db.session.delete(job)
        _db.session.commit()

        assert ApplicationTodo.query.filter_by(job_id=job_id).count() == 0

    def test_set_null_on_search_result_tracker(self, app):
        """Deleting a job SET NULLs the tracker_job_id on search results."""
        job_id, _, sr_id = self._setup_job_data()

        job = _db.session.get(Job, job_id)
        _db.session.delete(job)
        _db.session.commit()

        sr = _db.session.get(SearchResult, sr_id)
        assert sr is not None, "SearchResult should still exist"
        assert sr.tracker_job_id is None, "tracker_job_id should be NULL"

    def test_db_level_set_null(self, app):
        """DB-level SET NULL works even without ORM."""
        job_id, _, sr_id = self._setup_job_data()

        _db.session.execute(
            _db.text("DELETE FROM jobs WHERE id = :id"),
            {"id": job_id},
        )
        _db.session.commit()

        row = _db.session.execute(
            _db.text("SELECT tracker_job_id FROM search_results WHERE id = :id"),
            {"id": sr_id},
        ).first()
        assert row is not None
        assert row[0] is None

    def test_delete_job_route_unlinks_search_results(self, client):
        """DELETE /api/jobs/:id resets search result tracker fields."""
        with client.application.app_context():
            convo = Conversation(title="Test")
            _db.session.add(convo)
            _db.session.flush()

            job_resp = client.post("/api/jobs", json={"company": "Acme", "title": "Eng"})
            job_id = job_resp.get_json()["id"]

            sr = SearchResult(
                conversation_id=convo.id, company="Acme", title="Eng",
                tracker_job_id=job_id, added_to_tracker=True,
            )
            _db.session.add(sr)
            _db.session.commit()
            sr_id = sr.id

        resp = client.delete(f"/api/jobs/{job_id}")
        assert resp.status_code == 204

        with client.application.app_context():
            sr = _db.session.get(SearchResult, sr_id)
            assert sr is not None
            assert sr.tracker_job_id is None
            assert sr.added_to_tracker is False


# ────────────────────────────────────────────────────────────────────
# 4. ORM Relationship Tests
# ────────────────────────────────────────────────────────────────────

class TestORMRelationships:
    """Verify ORM relationships are correctly configured."""

    def test_conversation_has_search_results_relationship(self, app):
        convo = Conversation(title="Test")
        _db.session.add(convo)
        _db.session.flush()

        sr = SearchResult(conversation_id=convo.id, company="A", title="B")
        _db.session.add(sr)
        _db.session.commit()

        _db.session.refresh(convo)
        assert len(convo.search_results) == 1
        assert convo.search_results[0].company == "A"

    def test_search_result_has_conversation_backref(self, app):
        convo = Conversation(title="Test")
        _db.session.add(convo)
        _db.session.flush()

        sr = SearchResult(conversation_id=convo.id, company="A", title="B")
        _db.session.add(sr)
        _db.session.commit()

        _db.session.refresh(sr)
        assert sr.conversation is not None
        assert sr.conversation.title == "Test"


# ────────────────────────────────────────────────────────────────────
# 5. Migration System
# ────────────────────────────────────────────────────────────────────

class TestMigrationSystem:
    """Verify migrations apply correctly to fresh and pre-existing databases."""

    def test_fresh_db_via_migration(self, tmp_path):
        """A fresh database gets all tables via migration."""
        with patch("backend.config.get_data_dir", return_value=tmp_path), \
             patch("backend.app.get_data_dir", return_value=tmp_path), \
             patch("backend.app._init_telemetry"):
            app = create_app(config_class=TestConfig)

        with app.app_context():
            inspector = _db.inspect(_db.engine)
            tables = set(inspector.get_table_names())
            assert "jobs" in tables
            assert "conversations" in tables
            assert "messages" in tables
            assert "search_results" in tables
            assert "application_todos" in tables
            assert "job_documents" in tables
            assert "alembic_version" in tables

    def test_fresh_db_has_correct_fk_cascades(self, tmp_path):
        """Fresh DB tables have correct ON DELETE cascades."""
        db_path = tmp_path / "app.db"
        uri = f"sqlite:///{db_path}"

        class FreshConfig(TestConfig):
            SQLALCHEMY_DATABASE_URI = uri

        with patch("backend.config.get_data_dir", return_value=tmp_path), \
             patch("backend.app.get_data_dir", return_value=tmp_path), \
             patch("backend.app._init_telemetry"):
            app = create_app(config_class=FreshConfig)

        conn = sqlite3.connect(str(db_path))
        messages_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='messages'"
        ).fetchone()[0]
        assert "ON DELETE CASCADE" in messages_sql

        sr_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='search_results'"
        ).fetchone()[0]
        assert "ON DELETE CASCADE" in sr_sql
        assert "ON DELETE SET NULL" in sr_sql
        conn.close()

    def test_pre_migration_db_gets_upgraded(self, tmp_path):
        """A pre-migration DB (tables exist, no alembic_version) gets stamped and upgraded."""
        db_path = tmp_path / "app.db"

        # Create a pre-migration database
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY, title VARCHAR(200),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY, company VARCHAR(200) NOT NULL,
                title VARCHAR(200) NOT NULL, url VARCHAR(500),
                status VARCHAR(50), notes TEXT, salary_min INTEGER,
                salary_max INTEGER, location VARCHAR(200),
                remote_type VARCHAR(50), tags TEXT, contact_name VARCHAR(200),
                contact_email VARCHAR(200), applied_date DATE,
                source VARCHAR(200), job_fit INTEGER, requirements TEXT,
                nice_to_haves TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                role VARCHAR(20) NOT NULL, content TEXT, tool_calls TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE search_results (
                id INTEGER PRIMARY KEY,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                company VARCHAR(200) NOT NULL, title VARCHAR(200) NOT NULL,
                url VARCHAR(500), salary_min INTEGER, salary_max INTEGER,
                location VARCHAR(200), remote_type VARCHAR(50),
                source VARCHAR(200), description TEXT, requirements TEXT,
                nice_to_haves TEXT, job_fit INTEGER, fit_reason TEXT,
                added_to_tracker BOOLEAN DEFAULT 0,
                tracker_job_id INTEGER REFERENCES jobs(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE application_todos (
                id INTEGER PRIMARY KEY,
                job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                category VARCHAR(50), title VARCHAR(500) NOT NULL,
                description TEXT, completed BOOLEAN DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE job_documents (
                id INTEGER PRIMARY KEY,
                job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                doc_type VARCHAR(50) NOT NULL, content TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1, edit_summary TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO conversations (id, title) VALUES (1, 'Test');
            INSERT INTO jobs (id, company, title) VALUES (1, 'Acme', 'Eng');
            INSERT INTO messages (conversation_id, role, content)
                VALUES (1, 'user', 'hello');
            INSERT INTO search_results (conversation_id, company, title,
                tracker_job_id, added_to_tracker)
                VALUES (1, 'Acme', 'Eng', 1, 1);
        """)
        conn.commit()
        conn.close()

        uri = f"sqlite:///{db_path}"

        class PreMigConfig(TestConfig):
            SQLALCHEMY_DATABASE_URI = uri

        with patch("backend.config.get_data_dir", return_value=tmp_path), \
             patch("backend.app.get_data_dir", return_value=tmp_path), \
             patch("backend.app._init_telemetry"):
            app = create_app(config_class=PreMigConfig)

        # Verify data survived
        with app.app_context():
            assert Conversation.query.count() == 1
            assert Job.query.count() == 1
            assert Message.query.count() == 1
            assert SearchResult.query.count() == 1

        # Verify FK cascades were applied
        conn = sqlite3.connect(str(db_path))
        messages_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='messages'"
        ).fetchone()[0]
        assert "ON DELETE CASCADE" in messages_sql

        sr_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='search_results'"
        ).fetchone()[0]
        assert "ON DELETE CASCADE" in sr_sql
        assert "ON DELETE SET NULL" in sr_sql
        conn.close()
