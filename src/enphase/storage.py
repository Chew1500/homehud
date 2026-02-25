"""SQLite storage for solar production readings and daily summaries."""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime

log = logging.getLogger("home-hud.enphase.storage")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    production_w REAL,
    consumption_w REAL,
    net_w REAL,
    production_wh REAL,
    consumption_wh REAL,
    temperature_c REAL,
    cloud_cover_pct REAL,
    weather_code INTEGER
);
CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(timestamp);

CREATE TABLE IF NOT EXISTS inverter_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    serial_number TEXT NOT NULL,
    watts REAL,
    max_watts REAL
);

CREATE TABLE IF NOT EXISTS daily_summary (
    date TEXT PRIMARY KEY,
    total_production_wh REAL,
    total_consumption_wh REAL,
    peak_production_w REAL,
    avg_temperature_c REAL,
    avg_cloud_cover_pct REAL,
    reading_count INTEGER
);
"""


class SolarStorage:
    """Thread-safe SQLite storage for solar production data."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def store_reading(
        self,
        production_w: float,
        consumption_w: float,
        net_w: float,
        production_wh: float,
        consumption_wh: float,
        temperature_c: float | None = None,
        cloud_cover_pct: float | None = None,
        weather_code: int | None = None,
    ) -> None:
        """Store a production reading with optional weather data."""
        ts = datetime.now().isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO readings "
                "(timestamp, production_w, consumption_w, net_w, "
                "production_wh, consumption_wh, temperature_c, cloud_cover_pct, weather_code) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, production_w, consumption_w, net_w,
                 production_wh, consumption_wh, temperature_c, cloud_cover_pct, weather_code),
            )
            self._conn.commit()

    def store_inverter_readings(self, inverters: list[dict]) -> None:
        """Store per-inverter readings."""
        ts = datetime.now().isoformat()
        with self._lock:
            self._conn.executemany(
                "INSERT INTO inverter_readings (timestamp, serial_number, watts, max_watts) "
                "VALUES (?, ?, ?, ?)",
                [(ts, inv["serial"], inv.get("watts", 0), inv.get("max_watts", 0))
                 for inv in inverters],
            )
            self._conn.commit()

    def update_daily_summary(self, date: str) -> None:
        """Recompute daily summary from readings for the given date (YYYY-MM-DD)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT "
                "  MAX(production_wh) as total_production_wh, "
                "  MAX(consumption_wh) as total_consumption_wh, "
                "  MAX(production_w) as peak_production_w, "
                "  AVG(temperature_c) as avg_temperature_c, "
                "  AVG(cloud_cover_pct) as avg_cloud_cover_pct, "
                "  COUNT(*) as reading_count "
                "FROM readings WHERE timestamp LIKE ?",
                (f"{date}%",),
            ).fetchone()

            if row and row["reading_count"] > 0:
                self._conn.execute(
                    "INSERT OR REPLACE INTO daily_summary "
                    "(date, total_production_wh, total_consumption_wh, peak_production_w, "
                    "avg_temperature_c, avg_cloud_cover_pct, reading_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (date, row["total_production_wh"], row["total_consumption_wh"],
                     row["peak_production_w"], row["avg_temperature_c"],
                     row["avg_cloud_cover_pct"], row["reading_count"]),
                )
                self._conn.commit()

    def get_latest(self) -> dict | None:
        """Get the most recent production reading."""
        row = self._conn.execute(
            "SELECT * FROM readings ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def get_today_summary(self) -> dict | None:
        """Get today's daily summary."""
        today = datetime.now().strftime("%Y-%m-%d")
        row = self._conn.execute(
            "SELECT * FROM daily_summary WHERE date = ?", (today,)
        ).fetchone()
        return dict(row) if row else None

    def get_daily_summaries(self, days: int = 30) -> list[dict]:
        """Get daily summaries for the last N days."""
        rows = self._conn.execute(
            "SELECT * FROM daily_summary ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_similar_days(self, temp_c: float, tolerance: float = 5.0) -> list[dict]:
        """Get daily summaries for days with similar temperature."""
        rows = self._conn.execute(
            "SELECT * FROM daily_summary "
            "WHERE avg_temperature_c BETWEEN ? AND ? "
            "ORDER BY date DESC LIMIT 30",
            (temp_c - tolerance, temp_c + tolerance),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_date_readings(self, date: str) -> list[dict]:
        """Get all readings for a specific date (for LLM context)."""
        rows = self._conn.execute(
            "SELECT * FROM readings WHERE timestamp LIKE ? ORDER BY timestamp",
            (f"{date}%",),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
