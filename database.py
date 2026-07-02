"""SQLite database layer for GPS media metadata.

Uses WAL mode for better concurrent read performance.
Auto-simplifies result sets above 5000 points at low zoom levels.
"""

import sqlite3
import logging
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH: str = "geo_data.db"
MAX_POINTS: int = 5000


def get_connection() -> sqlite3.Connection:
    """Open a WAL-mode connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -8000")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create the media table and indexes if they don't exist."""
    with get_connection() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS media
               (path TEXT PRIMARY KEY,
                lat REAL,
                lon REAL,
                altitude REAL,
                timestamp DATETIME,
                modified_time DATETIME)"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS timestamp_idx ON media (timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS lat_lon_idx ON media (lat, lon)")
    logger.info("Database initialised (WAL mode).")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def count_records() -> int:
    """Return the total number of media records."""
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]


def get_data(
    bounds: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    skip_simplify: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Fetch media points, optionally filtered by spatial bounds and time range.

    Returns
    -------
    (points, top_addresses, total_count)
        ``points`` is the (possibly simplified) list of matching rows.
        ``top_addresses`` are the 5 most common lat/lon grids in the result.
        ``total_count`` is the count before simplification.
    """
    conditions: list[str] = []
    params: list[Any] = []

    if bounds:
        lat1, lng1, lat2, lng2 = map(float, bounds.split(","))
        conditions.append(
            "(lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?)"
        )
        params += [min(lat1, lat2), max(lat1, lat2), min(lng1, lng2), max(lng1, lng2)]

    if start_time and end_time:
        conditions.append("(timestamp BETWEEN ? AND ?)")
        params += [start_time, end_time]

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    with get_connection() as conn:
        # Main data query
        rows = conn.execute(
            f"SELECT path, lat, lon, altitude, timestamp FROM media{where} ORDER BY timestamp ASC",
            params,
        ).fetchall()

    total_count = len(rows)

    # Auto-simplification for large datasets at low zoom
    if not skip_simplify and total_count > MAX_POINTS:
        step = max(1, total_count // MAX_POINTS)
        rows = rows[::step]
        logger.debug("Simplified %d → %d points (every %dth)", total_count, len(rows), step)

    points = [
        {
            "path": row["path"],
            "lat": row["lat"],
            "lng": row["lon"],
            "altitude": row["altitude"],
            "timestamp": row["timestamp"],
            "sort_time": row["timestamp"],
        }
        for row in rows
    ]

    # Top-5 frequent location grids
    with get_connection() as conn:
        grid_rows = conn.execute(
            f"""SELECT ROUND(lat, 1) AS lat_grid,
                       ROUND(lon, 1) AS lon_grid,
                       COUNT(*) AS cnt
                FROM media{where}
                GROUP BY lat_grid, lon_grid
                ORDER BY cnt DESC
                LIMIT 5""",
            params,
        ).fetchall()

    addresses = [
        {"lat": r["lat_grid"], "lng": r["lon_grid"], "count": r["cnt"]}
        for r in grid_rows
    ]

    return points, addresses, total_count


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def get_modified_time(path: str) -> Any | None:
    """Return the stored mtime for *path*, or None if not in DB."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT modified_time FROM media WHERE path=?", (path,)
        ).fetchone()
        return row["modified_time"] if row else None


def upsert_media(records: list[tuple[Any, ...]]) -> None:
    """Insert or replace a batch of media records.

    Each record: (path, lat, lon, altitude, timestamp, modified_time)
    """
    with get_connection() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO media
               (path, lat, lon, altitude, timestamp, modified_time)
               VALUES (?,?,?,?,?,?)""",
            records,
        )
    logger.debug("Upserted %d records", len(records))


# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------

def get_all_timestamps() -> list[str]:
    """Return distinct dates that have media entries, sorted."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT DATE(timestamp) AS d FROM media ORDER BY d"
        ).fetchall()
        return [row["d"] for row in rows]


def get_daily_counts() -> dict[str, int]:
    """Return {date: photo_count} for every day that has media."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT DATE(timestamp) AS d, COUNT(*) AS cnt
               FROM media GROUP BY d ORDER BY d"""
        ).fetchall()
        return {row["d"]: row["cnt"] for row in rows}
