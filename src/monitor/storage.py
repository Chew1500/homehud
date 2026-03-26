"""SQLite storage for service monitoring — service definitions and check results."""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime

log = logging.getLogger("home-hud.monitor.storage")

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    check_type TEXT NOT NULL DEFAULT 'http',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS check_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    checked_at TEXT NOT NULL,
    is_up INTEGER NOT NULL,
    response_time_ms REAL,
    status_code INTEGER,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_check_results_service_time
    ON check_results(service_id, checked_at);
CREATE INDEX IF NOT EXISTS idx_check_results_time
    ON check_results(checked_at);
"""


class MonitorStorage:
    """Thread-safe SQLite storage for service monitoring data."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- Service CRUD --

    def add_service(
        self, name: str, url: str, check_type: str = "http"
    ) -> int:
        """Add a service to monitor. Returns the new service ID."""
        ts = datetime.now().isoformat()
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO services (name, url, check_type, created_at) "
                "VALUES (?, ?, ?, ?)",
                (name, url, check_type, ts),
            )
            self._conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def remove_service(self, service_id: int) -> bool:
        """Remove a service and its check history. Returns True if found."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM services WHERE id = ?", (service_id,)
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def toggle_service(self, service_id: int, enabled: bool) -> bool:
        """Enable or disable a service. Returns True if found."""
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE services SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, service_id),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def get_services(self, enabled_only: bool = False) -> list[dict]:
        """Get all services, optionally filtered to enabled only."""
        sql = "SELECT * FROM services"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY name"
        rows = self._conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

    def get_service(self, service_id: int) -> dict | None:
        """Get a single service by ID."""
        row = self._conn.execute(
            "SELECT * FROM services WHERE id = ?", (service_id,)
        ).fetchone()
        return dict(row) if row else None

    # -- Check results --

    def store_result(
        self,
        service_id: int,
        is_up: bool,
        response_time_ms: float | None = None,
        status_code: int | None = None,
        error: str | None = None,
    ) -> None:
        """Store a check result."""
        ts = datetime.now().isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO check_results "
                "(service_id, checked_at, is_up, response_time_ms, status_code, error) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (service_id, ts, 1 if is_up else 0, response_time_ms, status_code, error),
            )
            self._conn.commit()

    def get_latest_results(self) -> list[dict]:
        """Get the most recent check result for each service."""
        rows = self._conn.execute(
            "SELECT s.id, s.name, s.url, s.check_type, s.enabled, "
            "  cr.checked_at, cr.is_up, cr.response_time_ms, cr.status_code, cr.error "
            "FROM services s "
            "LEFT JOIN check_results cr ON cr.id = ("
            "  SELECT id FROM check_results "
            "  WHERE service_id = s.id ORDER BY checked_at DESC LIMIT 1"
            ") "
            "ORDER BY s.name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_down_services(self) -> list[dict]:
        """Get enabled services whose most recent check was down."""
        rows = self._conn.execute(
            "SELECT s.id, s.name, s.url, cr.checked_at, cr.error "
            "FROM services s "
            "JOIN check_results cr ON cr.id = ("
            "  SELECT id FROM check_results "
            "  WHERE service_id = s.id ORDER BY checked_at DESC LIMIT 1"
            ") "
            "WHERE s.enabled = 1 AND cr.is_up = 0 "
            "ORDER BY s.name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_service_history(
        self, service_id: int, days: int = 90
    ) -> list[dict]:
        """Get check history for a service over the last N days."""
        rows = self._conn.execute(
            "SELECT checked_at, is_up, response_time_ms, status_code, error "
            "FROM check_results "
            "WHERE service_id = ? "
            "  AND checked_at >= datetime('now', ?)"
            "ORDER BY checked_at",
            (service_id, f"-{days} days"),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_uptime_summary(
        self, service_id: int, days: int = 30
    ) -> dict:
        """Get uptime percentage and avg response time over the last N days."""
        row = self._conn.execute(
            "SELECT "
            "  COUNT(*) as total_checks, "
            "  SUM(is_up) as up_checks, "
            "  AVG(CASE WHEN is_up = 1 THEN response_time_ms END) as avg_response_ms "
            "FROM check_results "
            "WHERE service_id = ? "
            "  AND checked_at >= datetime('now', ?)",
            (service_id, f"-{days} days"),
        ).fetchone()
        if not row or row["total_checks"] == 0:
            return {"uptime_pct": None, "avg_response_ms": None, "total_checks": 0}
        return {
            "uptime_pct": round(row["up_checks"] / row["total_checks"] * 100, 2),
            "avg_response_ms": round(row["avg_response_ms"], 1) if row["avg_response_ms"] else None,
            "total_checks": row["total_checks"],
        }

    # -- Maintenance --

    def prune_old_results(self, max_age_days: int = 90) -> int:
        """Delete check results older than max_age_days. Returns rows deleted."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM check_results WHERE checked_at < datetime('now', ?)",
                (f"-{max_age_days} days",),
            )
            self._conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                log.info("Pruned %d check results older than %d days", deleted, max_age_days)
            return deleted

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
