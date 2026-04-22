import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from app.config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    is_new_db = not DB_PATH.exists()
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                request_json TEXT NOT NULL,
                comments_json TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                error TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session_created "
            "ON messages(session_id, created_at)"
        )
        if is_new_db:
            _seed_initial_data(conn)


def _seed_initial_data(conn: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc).isoformat()
    session_id = str(uuid4())
    conn.execute(
        """
        INSERT INTO sessions (session_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, "Welcome to CommentGen", now, now),
    )
    conn.execute(
        """
        INSERT INTO messages (message_id, session_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            session_id,
            "assistant",
            "Welcome to CommentGen. Share a post or screenshot to generate one reply.",
            now,
        ),
    )
