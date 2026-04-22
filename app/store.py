import json
from typing import Dict, List, Optional

from app.db import get_conn


def save_run(run_id: str, payload: Dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, status, agent_name, request_json, comments_json,
                provider, model, created_at, completed_at, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                status=excluded.status,
                agent_name=excluded.agent_name,
                request_json=excluded.request_json,
                comments_json=excluded.comments_json,
                provider=excluded.provider,
                model=excluded.model,
                created_at=excluded.created_at,
                completed_at=excluded.completed_at,
                error=excluded.error
            """,
            (
                run_id,
                payload["status"],
                payload.get("agent_name", "comment_reply"),
                json.dumps(payload.get("request", {})),
                json.dumps(payload.get("comments", [])),
                payload.get("provider", "unknown"),
                payload.get("model", "unknown"),
                payload["created_at"],
                payload.get("completed_at"),
                payload.get("error"),
            ),
        )


def load_run(run_id: str) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "run_id": row["run_id"],
        "status": row["status"],
        "agent_name": row["agent_name"],
        "request": json.loads(row["request_json"]),
        "comments": json.loads(row["comments_json"]),
        "provider": row["provider"],
        "model": row["model"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
        "error": row["error"],
    }


def create_session(session_id: str, title: str, created_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions (session_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, title, created_at, created_at),
        )


def update_session_title(session_id: str, title: str, updated_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
            (title, updated_at, session_id),
        )


def touch_session(session_id: str, updated_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (updated_at, session_id),
        )


def list_sessions() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT session_id, title, created_at, updated_at
            FROM sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return [
        {
            "session_id": row["session_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def get_session(session_id: str) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT session_id, title, created_at, updated_at
            FROM sessions WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "session_id": row["session_id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def add_message(
    message_id: str,
    session_id: str,
    role: str,
    content: str,
    created_at: str,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO messages (message_id, session_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (message_id, session_id, role, content, created_at),
        )


def list_messages(session_id: str) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT message_id, session_id, role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        ).fetchall()
    return [
        {
            "message_id": row["message_id"],
            "session_id": row["session_id"],
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
