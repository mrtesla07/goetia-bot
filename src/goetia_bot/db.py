import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class UserRecord:
    tg_id: int
    passthrough: bool = False
    schedule_enabled: bool = False
    schedule_time: str = "10:00"
    session_path: Optional[str] = None


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_id INTEGER UNIQUE NOT NULL,
                    passthrough INTEGER DEFAULT 0,
                    schedule_enabled INTEGER DEFAULT 0,
                    schedule_time TEXT DEFAULT '10:00',
                    session_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()

    def upsert_user(self, tg_id: int) -> UserRecord:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (tg_id) VALUES (?)
                ON CONFLICT(tg_id) DO NOTHING;
                """,
                (tg_id,),
            )
            conn.commit()
        return self.get_user(tg_id)

    def get_user(self, tg_id: int) -> Optional[UserRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tg_id, passthrough, schedule_enabled, schedule_time, session_path FROM users WHERE tg_id = ?",
                (tg_id,),
            ).fetchone()
            if not row:
                return None
            return UserRecord(
                tg_id=row["tg_id"],
                passthrough=bool(row["passthrough"]),
                schedule_enabled=bool(row["schedule_enabled"]),
                schedule_time=row["schedule_time"],
                session_path=row["session_path"],
            )

    def set_session_path(self, tg_id: int, session_path: Optional[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET session_path = ?, updated_at = CURRENT_TIMESTAMP WHERE tg_id = ?",
                (session_path, tg_id),
            )
            conn.commit()

    def set_passthrough(self, tg_id: int, enabled: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET passthrough = ?, updated_at = CURRENT_TIMESTAMP WHERE tg_id = ?",
                (int(enabled), tg_id),
            )
            conn.commit()

    def set_schedule(self, tg_id: int, enabled: bool, time_str: Optional[str] = None) -> None:
        with self._connect() as conn:
            if time_str:
                conn.execute(
                    "UPDATE users SET schedule_enabled = ?, schedule_time = ?, updated_at = CURRENT_TIMESTAMP WHERE tg_id = ?",
                    (int(enabled), time_str, tg_id),
                )
            else:
                conn.execute(
                    "UPDATE users SET schedule_enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE tg_id = ?",
                    (int(enabled), tg_id),
                )
            conn.commit()

    def set_schedule_time(self, tg_id: int, time_str: str) -> None:
        user = self.get_user(tg_id)
        self.set_schedule(tg_id, user.schedule_enabled if user else False, time_str)

    def list_users(self) -> Dict[int, UserRecord]:
        result: Dict[int, UserRecord] = {}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT tg_id, passthrough, schedule_enabled, schedule_time, session_path FROM users"
            ).fetchall()
            for row in rows:
                result[row["tg_id"]] = UserRecord(
                    tg_id=row["tg_id"],
                    passthrough=bool(row["passthrough"]),
                    schedule_enabled=bool(row["schedule_enabled"]),
                    schedule_time=row["schedule_time"],
                    session_path=row["session_path"],
                )
        return result

    def clear_user(self, tg_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET session_path = NULL, passthrough = 0, schedule_enabled = 0, updated_at = CURRENT_TIMESTAMP WHERE tg_id = ?",
                (tg_id,),
            )
            conn.commit()
