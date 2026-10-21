from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from ..models.artifact import Artifact
from ..models.message import Message
from ..models.task import Task, TaskState, TaskStatus, now_utc_iso
from .base import BaseTaskStore


class SqliteTaskStore(BaseTaskStore):
    def __init__(self, connection_or_path: sqlite3.Connection | str) -> None:
        if isinstance(connection_or_path, str):
            self.conn = sqlite3.connect(connection_or_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        else:
            self.conn = connection_or_path
            self.conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS a2a_tasks (
                    task_id TEXT PRIMARY KEY,
                    context_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    status_message TEXT,
                    status_details JSON,
                    metadata JSON,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_a2a_tasks_context ON a2a_tasks(context_id);
                CREATE INDEX IF NOT EXISTS idx_a2a_tasks_state ON a2a_tasks(state);

                CREATE TABLE IF NOT EXISTS a2a_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    parts JSON NOT NULL,
                    context_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES a2a_tasks(task_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_a2a_messages_task ON a2a_messages(task_id);

                CREATE TABLE IF NOT EXISTS a2a_artifacts (
                    artifact_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(artifact_id, task_id),
                    FOREIGN KEY(task_id) REFERENCES a2a_tasks(task_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_a2a_artifacts_task ON a2a_artifacts(task_id);
                """
            )

    def create_task(
        self,
        task_id: str,
        context_id: str,
        initial_message: Message | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        now = now_utc_iso()
        status = TaskStatus(
            state=TaskState.SUBMITTED,
            message="Task created",
            timestamp=now,
        )
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO a2a_tasks (task_id, context_id, state, status_message, status_details, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    context_id,
                    status.state.value,
                    status.message,
                    json.dumps(status.details) if status.details else None,
                    json.dumps(metadata) if metadata else None,
                    now,
                    now,
                ),
            )
            history = []
            if initial_message:
                self.append_message(task_id, initial_message)
                history.append(initial_message)

            return Task(
                id=task_id,
                context_id=context_id,
                status=status,
                history=history,
                artifacts=[],
                metadata=metadata or {},
            )

    def update_status(
        self,
        task_id: str,
        state: TaskState,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> TaskStatus:
        now = now_utc_iso()
        status = TaskStatus(
            state=state,
            message=message,
            details=details,
            timestamp=now,
        )
        with self._lock, self.conn:
            cursor = self.conn.execute(
                """
                UPDATE a2a_tasks
                SET state = ?, status_message = ?, status_details = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    status.state.value,
                    status.message,
                    json.dumps(details) if details else None,
                    now,
                    task_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Task {task_id} not found")
        return status

    def append_message(self, task_id: str, message: Message) -> None:
        parts_data = []
        for p in message.parts:
            if hasattr(p, "to_dict"):
                parts_data.append(p.to_dict())
            elif isinstance(p, dict):
                parts_data.append(p)
        now = message.created_at or now_utc_iso()
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO a2a_messages (task_id, role, parts, context_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    message.role,
                    json.dumps(parts_data),
                    message.context_id,
                    now,
                ),
            )

    def add_artifact(self, task_id: str, artifact: Artifact) -> None:
        now = artifact.created_at or now_utc_iso()
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO a2a_artifacts (artifact_id, task_id, name, mime_type, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    task_id,
                    artifact.name,
                    artifact.mime_type,
                    json.dumps(artifact.data),
                    now,
                ),
            )

    def get_task(self, task_id: str) -> Task | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM a2a_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None

            msg_rows = self.conn.execute(
                "SELECT * FROM a2a_messages WHERE task_id = ? ORDER BY id ASC",
                (task_id,),
            ).fetchall()
            history: list[Message] = []
            for mr in msg_rows:
                parts = json.loads(mr["parts"]) if mr["parts"] else []
                history.append(
                    Message.from_dict({
                        "role": mr["role"],
                        "parts": parts,
                        "contextId": mr["context_id"],
                        "createdAt": mr["created_at"],
                    })
                )

            art_rows = self.conn.execute(
                "SELECT * FROM a2a_artifacts WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()
            artifacts: list[Artifact] = []
            for ar in art_rows:
                data = json.loads(ar["data"]) if ar["data"] else None
                artifacts.append(
                    Artifact(
                        artifact_id=ar["artifact_id"],
                        name=ar["name"],
                        mime_type=ar["mime_type"],
                        data=data,
                        created_at=ar["created_at"],
                    )
                )

            meta = json.loads(row["metadata"]) if row["metadata"] else {}
            details = json.loads(row["status_details"]) if row["status_details"] else None
            status = TaskStatus(
                state=TaskState.from_str(row["state"]),
                message=row["status_message"],
                details=details,
                timestamp=row["updated_at"],
            )

            return Task(
                id=row["task_id"],
                context_id=row["context_id"],
                status=status,
                history=history,
                artifacts=artifacts,
                metadata=meta,
            )

    def list_tasks(
        self,
        context_id: str | None = None,
        state: TaskState | None = None,
        limit: int = 50,
    ) -> list[Task]:
        query = "SELECT task_id FROM a2a_tasks"
        conditions = []
        params: list[Any] = []
        if context_id:
            conditions.append("context_id = ?")
            params.append(context_id)
        if state:
            conditions.append("state = ?")
            params.append(state.value)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self.conn.execute(query, tuple(params)).fetchall()
            tasks: list[Task] = []
            for r in rows:
                t = self.get_task(r["task_id"])
                if t:
                    tasks.append(t)
            return tasks
