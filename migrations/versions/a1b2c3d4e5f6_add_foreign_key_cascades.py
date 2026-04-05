"""add foreign key cascades

Adds ON DELETE CASCADE / SET NULL to foreign keys that were previously
missing cascade rules.  SQLite cannot ALTER constraints in-place, so we
recreate the affected tables via the standard SQLite rename-and-copy
pattern.

Affected tables:
  - messages.conversation_id  → ON DELETE CASCADE
  - search_results.conversation_id → ON DELETE CASCADE
  - search_results.tracker_job_id  → ON DELETE SET NULL

Revision ID: a1b2c3d4e5f6
Revises: 2d18089fe7f9
Create Date: 2026-04-04 17:15:00.000000

"""
from alembic import op


revision = 'a1b2c3d4e5f6'
down_revision = '2d18089fe7f9'
branch_labels = None
depends_on = None


def _recreate_table(old_name, new_ddl, columns):
    """Recreate a SQLite table with a new schema, preserving data.

    Uses the standard SQLite pattern: create new → copy data → drop old → rename.
    """
    tmp_name = f"_{old_name}_new"
    col_list = ", ".join(columns)
    op.execute(new_ddl.replace(f'"{old_name}"', f'"{tmp_name}"'))
    op.execute(f'INSERT INTO "{tmp_name}" ({col_list}) SELECT {col_list} FROM "{old_name}"')
    op.execute(f'DROP TABLE "{old_name}"')
    op.execute(f'ALTER TABLE "{tmp_name}" RENAME TO "{old_name}"')


_MESSAGES_COLS = ['id', 'conversation_id', 'role', 'content', 'tool_calls', 'created_at']

_MESSAGES_NEW = '''
CREATE TABLE "messages" (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT,
    tool_calls TEXT,
    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP)
)
'''

_MESSAGES_OLD = '''
CREATE TABLE "messages" (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role VARCHAR(20) NOT NULL,
    content TEXT,
    tool_calls TEXT,
    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP)
)
'''

_SEARCH_RESULTS_COLS = [
    'id', 'conversation_id', 'company', 'title', 'url',
    'salary_min', 'salary_max', 'location', 'remote_type', 'source',
    'description', 'requirements', 'nice_to_haves',
    'job_fit', 'fit_reason', 'added_to_tracker', 'tracker_job_id', 'created_at',
]

_SEARCH_RESULTS_NEW = '''
CREATE TABLE "search_results" (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    company VARCHAR(200) NOT NULL,
    title VARCHAR(200) NOT NULL,
    url VARCHAR(500),
    salary_min INTEGER,
    salary_max INTEGER,
    location VARCHAR(200),
    remote_type VARCHAR(50),
    source VARCHAR(200),
    description TEXT,
    requirements TEXT,
    nice_to_haves TEXT,
    job_fit INTEGER,
    fit_reason TEXT,
    added_to_tracker BOOLEAN DEFAULT 0,
    tracker_job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP)
)
'''

_SEARCH_RESULTS_OLD = '''
CREATE TABLE "search_results" (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    company VARCHAR(200) NOT NULL,
    title VARCHAR(200) NOT NULL,
    url VARCHAR(500),
    salary_min INTEGER,
    salary_max INTEGER,
    location VARCHAR(200),
    remote_type VARCHAR(50),
    source VARCHAR(200),
    description TEXT,
    requirements TEXT,
    nice_to_haves TEXT,
    job_fit INTEGER,
    fit_reason TEXT,
    added_to_tracker BOOLEAN DEFAULT 0,
    tracker_job_id INTEGER REFERENCES jobs(id),
    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP)
)
'''


def upgrade():
    _recreate_table('messages', _MESSAGES_NEW, _MESSAGES_COLS)
    _recreate_table('search_results', _SEARCH_RESULTS_NEW, _SEARCH_RESULTS_COLS)


def downgrade():
    _recreate_table('search_results', _SEARCH_RESULTS_OLD, _SEARCH_RESULTS_COLS)
    _recreate_table('messages', _MESSAGES_OLD, _MESSAGES_COLS)
