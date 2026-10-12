import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "reviews.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive column migrations for DBs created before a schema change."""
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(submission_files)")}
    if "object_key" not in existing_cols:
        conn.execute("ALTER TABLE submission_files ADD COLUMN object_key TEXT")
    if "kind_source" not in existing_cols:
        conn.execute("ALTER TABLE submission_files ADD COLUMN kind_source TEXT NOT NULL DEFAULT 'heuristic'")

    module_cols = {row[1] for row in conn.execute("PRAGMA table_info(modules)")}
    if "briefing_json" not in module_cols:
        conn.execute("ALTER TABLE modules ADD COLUMN briefing_json TEXT")

    chat_cols = {row[1] for row in conn.execute("PRAGMA table_info(chat_messages)")}
    if "trace_json" not in chat_cols:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN trace_json TEXT")
    class_chat_cols = {row[1] for row in conn.execute("PRAGMA table_info(class_chat_messages)")}
    if "trace_json" not in class_chat_cols:
        conn.execute("ALTER TABLE class_chat_messages ADD COLUMN trace_json TEXT")

    # ai_usage_log.kind's CHECK constraint predates the research/review/grade/briefing
    # pipeline stages - SQLite can't ALTER a CHECK constraint, so rebuild the table.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='ai_usage_log'"
    ).fetchone()
    if row and "'gap_analysis'" not in row[0]:
        conn.execute("ALTER TABLE ai_usage_log RENAME TO ai_usage_log_old")
        conn.execute("""
            CREATE TABLE ai_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
                module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
                yukta_session_id TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'assist' CHECK (kind IN ('assist', 'chat', 'briefing', 'research', 'review', 'grade', 'gap_analysis')),
                tokens_prompt INTEGER NOT NULL DEFAULT 0,
                tokens_completion INTEGER NOT NULL DEFAULT 0,
                iterations INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            INSERT INTO ai_usage_log (id, student_id, module_id, yukta_session_id, kind, tokens_prompt, tokens_completion, iterations, created_at)
            SELECT id, student_id, module_id, yukta_session_id, kind, tokens_prompt, tokens_completion, iterations, created_at FROM ai_usage_log_old
        """)
        conn.execute("DROP TABLE ai_usage_log_old")

    # review_status.status's CHECK constraint predates 'not_submitted' - rebuild the table.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='review_status'"
    ).fetchone()
    if row and "'not_submitted'" not in row[0]:
        conn.execute("ALTER TABLE review_status RENAME TO review_status_old")
        conn.execute("""
            CREATE TABLE review_status (
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
                framing_note TEXT,
                total_weighted_score REAL,
                band TEXT,
                status TEXT NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'completed', 'not_submitted')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (student_id, module_id)
            )
        """)
        conn.execute("""
            INSERT INTO review_status (student_id, module_id, framing_note, total_weighted_score, band, status, updated_at)
            SELECT student_id, module_id, framing_note, total_weighted_score, band, status, updated_at FROM review_status_old
        """)
        conn.execute("DROP TABLE review_status_old")

    conn.commit()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text())
        conn.commit()
        _migrate(conn)
    finally:
        conn.close()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()
