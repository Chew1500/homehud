"""SQLite storage for media discovery — library cache, taste profile, recommendations."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime

log = logging.getLogger("home-hud.discovery.storage")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    media_type TEXT NOT NULL,  -- "movie" or "series"
    year INTEGER,
    genres TEXT,               -- JSON array
    rating_imdb REAL,
    rating_tmdb REAL,
    rating_rt REAL,
    studio TEXT,
    runtime INTEGER,
    certification TEXT,
    overview TEXT,
    played INTEGER DEFAULT 0,
    play_count INTEGER DEFAULT 0,
    is_favorite INTEGER DEFAULT 0,
    source TEXT,               -- "radarr", "sonarr", "jellyfin"
    synced_at TEXT,
    UNIQUE(external_id, media_type)
);
CREATE INDEX IF NOT EXISTS idx_library_type ON library(media_type);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    role TEXT,
    type TEXT,                 -- "Actor", "Director", "Writer"
    FOREIGN KEY (library_id) REFERENCES library(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_people_library ON people(library_id);
CREATE INDEX IF NOT EXISTS idx_people_type ON people(type);

CREATE TABLE IF NOT EXISTS taste_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dimension TEXT NOT NULL,   -- "genre", "actor", "director", "studio", "decade", "rating_range"
    value TEXT NOT NULL,
    score REAL NOT NULL,
    count INTEGER NOT NULL,
    UNIQUE(dimension, value)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    media_type TEXT NOT NULL,
    year INTEGER,
    reason TEXT,
    genres TEXT,               -- JSON array
    confidence REAL DEFAULT 0.5,
    status TEXT DEFAULT 'active',  -- "active", "dismissed", "tracked"
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_meta (
    source TEXT PRIMARY KEY,
    last_sync TEXT NOT NULL
);
"""


class DiscoveryStorage:
    """Thread-safe SQLite storage for media discovery data."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- Library --

    def upsert_library_item(self, item: dict) -> int:
        """Insert or update a library item. Returns the row id."""
        ts = datetime.now().isoformat()
        genres_json = json.dumps(item.get("genres", []))
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO library "
                "(external_id, title, media_type, year, genres, "
                "rating_imdb, rating_tmdb, rating_rt, studio, runtime, "
                "certification, overview, played, play_count, is_favorite, "
                "source, synced_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(external_id, media_type) DO UPDATE SET "
                "title=excluded.title, year=excluded.year, genres=excluded.genres, "
                "rating_imdb=excluded.rating_imdb, rating_tmdb=excluded.rating_tmdb, "
                "rating_rt=excluded.rating_rt, studio=excluded.studio, "
                "runtime=excluded.runtime, certification=excluded.certification, "
                "overview=excluded.overview, played=excluded.played, "
                "play_count=excluded.play_count, is_favorite=excluded.is_favorite, "
                "source=excluded.source, synced_at=excluded.synced_at",
                (
                    item["external_id"], item["title"], item["media_type"],
                    item.get("year"), genres_json,
                    item.get("rating_imdb"), item.get("rating_tmdb"),
                    item.get("rating_rt"), item.get("studio"),
                    item.get("runtime"), item.get("certification"),
                    item.get("overview"),
                    int(item.get("played", False)),
                    item.get("play_count", 0),
                    int(item.get("is_favorite", False)),
                    item.get("source", ""),
                    ts,
                ),
            )
            self._conn.commit()
            return cursor.lastrowid

    def get_library_item_id(self, external_id: str, media_type: str) -> int | None:
        """Get the row id for a library item by external_id and media_type."""
        row = self._conn.execute(
            "SELECT id FROM library WHERE external_id = ? AND media_type = ?",
            (external_id, media_type),
        ).fetchone()
        return row["id"] if row else None

    def get_library(self) -> list[dict]:
        """Get all library items."""
        rows = self._conn.execute(
            "SELECT * FROM library ORDER BY title"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_library_titles(self) -> list[str]:
        """Get all library titles (for dedup in recommendation prompts)."""
        rows = self._conn.execute(
            "SELECT title FROM library ORDER BY title"
        ).fetchall()
        return [r["title"] for r in rows]

    def get_library_count(self) -> int:
        """Get total library item count."""
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM library").fetchone()
        return row["cnt"]

    # -- People --

    def set_people(self, library_id: int, people: list[dict]) -> None:
        """Replace all people for a library item."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM people WHERE library_id = ?", (library_id,)
            )
            self._conn.executemany(
                "INSERT INTO people (library_id, name, role, type) "
                "VALUES (?, ?, ?, ?)",
                [
                    (library_id, p["name"], p.get("role", ""), p.get("type", ""))
                    for p in people
                ],
            )
            self._conn.commit()

    # -- Taste Profile --

    def rebuild_taste_profile(self) -> None:
        """Rebuild the taste profile from library data and people."""
        with self._lock:
            self._conn.execute("DELETE FROM taste_profile")
            self._build_genre_profile()
            self._build_people_profile()
            self._build_studio_profile()
            self._build_decade_profile()
            self._conn.commit()

    def _weight_for(self, played: int, is_favorite: int) -> float:
        """Compute weighting based on watch behavior."""
        if played and is_favorite:
            return 3.0
        if played:
            return 2.0
        return 1.0

    def _build_genre_profile(self) -> None:
        rows = self._conn.execute(
            "SELECT genres, played, is_favorite FROM library"
        ).fetchall()
        scores: dict[str, float] = {}
        counts: dict[str, int] = {}
        for row in rows:
            weight = self._weight_for(row["played"], row["is_favorite"])
            genres = json.loads(row["genres"]) if row["genres"] else []
            for genre in genres:
                scores[genre] = scores.get(genre, 0) + weight
                counts[genre] = counts.get(genre, 0) + 1
        for genre, score in scores.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO taste_profile (dimension, value, score, count) "
                "VALUES ('genre', ?, ?, ?)",
                (genre, score, counts[genre]),
            )

    def _build_people_profile(self) -> None:
        rows = self._conn.execute(
            "SELECT p.name, p.type, l.played, l.is_favorite "
            "FROM people p JOIN library l ON p.library_id = l.id "
            "WHERE p.type IN ('Actor', 'Director')"
        ).fetchall()
        scores: dict[tuple[str, str], float] = {}
        counts: dict[tuple[str, str], int] = {}
        for row in rows:
            weight = self._weight_for(row["played"], row["is_favorite"])
            dim = "actor" if row["type"] == "Actor" else "director"
            key = (dim, row["name"])
            scores[key] = scores.get(key, 0) + weight
            counts[key] = counts.get(key, 0) + 1
        for (dim, name), score in scores.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO taste_profile (dimension, value, score, count) "
                "VALUES (?, ?, ?, ?)",
                (dim, name, score, counts[(dim, name)]),
            )

    def _build_studio_profile(self) -> None:
        rows = self._conn.execute(
            "SELECT studio, played, is_favorite FROM library WHERE studio != ''"
        ).fetchall()
        scores: dict[str, float] = {}
        counts: dict[str, int] = {}
        for row in rows:
            weight = self._weight_for(row["played"], row["is_favorite"])
            studio = row["studio"]
            scores[studio] = scores.get(studio, 0) + weight
            counts[studio] = counts.get(studio, 0) + 1
        for studio, score in scores.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO taste_profile (dimension, value, score, count) "
                "VALUES ('studio', ?, ?, ?)",
                (studio, score, counts[studio]),
            )

    def _build_decade_profile(self) -> None:
        rows = self._conn.execute(
            "SELECT year, played, is_favorite FROM library WHERE year IS NOT NULL"
        ).fetchall()
        scores: dict[str, float] = {}
        counts: dict[str, int] = {}
        for row in rows:
            weight = self._weight_for(row["played"], row["is_favorite"])
            decade = f"{(row['year'] // 10) * 10}s"
            scores[decade] = scores.get(decade, 0) + weight
            counts[decade] = counts.get(decade, 0) + 1
        for decade, score in scores.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO taste_profile (dimension, value, score, count) "
                "VALUES ('decade', ?, ?, ?)",
                (decade, score, counts[decade]),
            )

    def get_taste_profile(self) -> list[dict]:
        """Get the full taste profile, sorted by score descending."""
        rows = self._conn.execute(
            "SELECT * FROM taste_profile ORDER BY score DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_taste_summary(self) -> str:
        """Get a compact text summary of the taste profile for LLM prompts."""
        profile = self.get_taste_profile()
        if not profile:
            return "No taste profile available yet."

        by_dim: dict[str, list[dict]] = {}
        for entry in profile:
            dim = entry["dimension"]
            by_dim.setdefault(dim, []).append(entry)

        parts = []
        for dim in ["genre", "director", "actor", "studio", "decade"]:
            entries = by_dim.get(dim, [])[:5]  # Top 5 per dimension
            if entries:
                values = ", ".join(
                    f"{e['value']}({e['score']:.1f})" for e in entries
                )
                parts.append(f"{dim}: {values}")

        return "; ".join(parts)

    # -- Recommendations --

    def add_recommendation(self, rec: dict) -> int:
        """Add a recommendation. Returns the row id."""
        ts = datetime.now().isoformat()
        genres_json = json.dumps(rec.get("genres", []))
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO recommendations "
                "(title, media_type, year, reason, genres, confidence, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec["title"], rec["media_type"], rec.get("year"),
                    rec.get("reason", ""), genres_json,
                    rec.get("confidence", 0.5), rec.get("status", "active"),
                    ts,
                ),
            )
            self._conn.commit()
            return cursor.lastrowid

    def get_active_recommendations(self) -> list[dict]:
        """Get all active recommendations, newest first."""
        rows = self._conn.execute(
            "SELECT * FROM recommendations WHERE status = 'active' "
            "ORDER BY confidence DESC, created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def dismiss_recommendation(self, rec_id: int) -> None:
        """Mark a recommendation as dismissed."""
        with self._lock:
            self._conn.execute(
                "UPDATE recommendations SET status = 'dismissed' WHERE id = ?",
                (rec_id,),
            )
            self._conn.commit()

    def track_recommendation(self, rec_id: int) -> None:
        """Mark a recommendation as tracked (added to library)."""
        with self._lock:
            self._conn.execute(
                "UPDATE recommendations SET status = 'tracked' WHERE id = ?",
                (rec_id,),
            )
            self._conn.commit()

    def clear_active_recommendations(self) -> None:
        """Remove all active recommendations (before regenerating)."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM recommendations WHERE status = 'active'"
            )
            self._conn.commit()

    # -- Sync Meta --

    def set_sync_time(self, source: str) -> None:
        """Record the last sync time for a source."""
        ts = datetime.now().isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO sync_meta (source, last_sync) VALUES (?, ?)",
                (source, ts),
            )
            self._conn.commit()

    def get_sync_time(self, source: str) -> str | None:
        """Get the last sync time for a source."""
        row = self._conn.execute(
            "SELECT last_sync FROM sync_meta WHERE source = ?", (source,)
        ).fetchone()
        return row["last_sync"] if row else None

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
