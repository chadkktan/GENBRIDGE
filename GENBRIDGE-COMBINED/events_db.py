"""
events_db.py - Events/Bookings SQLite helper (no ORM)

Usage in app.py:
    from database import get_db, list_events, get_event, create_booking, list_bookings, update_booking, delete_booking, clear_bookings
"""

from __future__ import annotations
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

# Put genbridge.db beside this file by default
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "genbridge_events.db")


def get_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Returns a SQLite connection with row factory enabled.
    Remember to .close() it when done.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def list_events(
    *,
    location: str = "",
    activity_type: str = "",
    from_date: str = "",   # "YYYY-MM-DD"
    to_date: str = "",     # "YYYY-MM-DD"
    db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    """
    Returns events (with audience list) filtered and sorted by date ascending.
    Dates in DB are stored as "YYYY-MM-DD HH:MM".
    """
    clauses = []
    params: List[Any] = []

    if location:
        clauses.append("LOWER(location) LIKE ?")
        params.append(f"%{location.lower()}%")

    if activity_type:
        clauses.append("LOWER(category) = ?")
        params.append(activity_type.lower())

    if from_date:
        # Compare date portion only
        clauses.append("substr(date, 1, 10) >= ?")
        params.append(from_date)

    if to_date:
        clauses.append("substr(date, 1, 10) <= ?")
        params.append(to_date)

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    conn = get_db(db_path)
    rows = conn.execute(
        f"SELECT * FROM events{where_sql} ORDER BY date ASC",
        params
    ).fetchall()

    events: List[Dict[str, Any]] = []
    for r in rows:
        ev = dict(r)
        aud = conn.execute(
            "SELECT label FROM event_audience WHERE event_id = ? ORDER BY label ASC",
            (ev["id"],)
        ).fetchall()
        ev["audience"] = [a["label"] for a in aud]
        ev["wheelchair"] = bool(ev["wheelchair"])
        events.append(ev)

    conn.close()
    return events


def get_event(event_id: int, *, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db(db_path)
    r = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not r:
        conn.close()
        return None

    ev = dict(r)
    aud = conn.execute(
        "SELECT label FROM event_audience WHERE event_id = ? ORDER BY label ASC",
        (event_id,)
    ).fetchall()
    ev["audience"] = [a["label"] for a in aud]
    ev["wheelchair"] = bool(ev["wheelchair"])
    conn.close()
    return ev


def decrement_spots_left(event_id: int, *, db_path: str = DB_PATH) -> bool:
    """
    Atomically decrements spots_left if spots_left > 0.
    Returns True if success, False if no spots left or event missing.
    """
    conn = get_db(db_path)
    cur = conn.execute(
        "UPDATE events SET spots_left = spots_left - 1 WHERE id = ? AND spots_left > 0",
        (event_id,)
    )
    conn.commit()
    ok = cur.rowcount == 1
    conn.close()
    return ok


def create_booking(
    *,
    event_id: int,
    first_name: str,
    last_name: str,
    contact: str,
    age_group: str,
    reg_type: str,
    saved_at: str,   # "YYYY-MM-DD HH:MM"
    db_path: str = DB_PATH
) -> int:
    conn = get_db(db_path)
    cur = conn.execute(
        """
        INSERT INTO bookings (event_id, first_name, last_name, contact, age_group, reg_type, saved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, first_name, last_name, contact, age_group, reg_type, saved_at)
    )
    conn.commit()
    booking_id = int(cur.lastrowid)
    conn.close()
    return booking_id


def list_bookings(*, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Returns bookings newest-first, joined with event info.
    """
    conn = get_db(db_path)
    rows = conn.execute(
        """
        SELECT
          b.id AS booking_id,
          b.event_id,
          b.first_name,
          b.last_name,
          b.contact,
          b.age_group,
          b.reg_type,
          b.saved_at,
          e.category,
          e.title,
          e.date,
          e.location
        FROM bookings b
        JOIN events e ON e.id = b.event_id
        ORDER BY b.id DESC
        """
    ).fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["full_name"] = f'{d["first_name"]} {d["last_name"]}'.strip()
        out.append(d)

    conn.close()
    return out


def get_booking(booking_id: int, *, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db(db_path)
    r = conn.execute(
        """
        SELECT
          b.id AS booking_id,
          b.event_id,
          b.first_name,
          b.last_name,
          b.contact,
          b.age_group,
          b.reg_type,
          b.saved_at,
          e.category,
          e.title,
          e.date,
          e.location
        FROM bookings b
        JOIN events e ON e.id = b.event_id
        WHERE b.id = ?
        """,
        (booking_id,)
    ).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    d["full_name"] = f'{d["first_name"]} {d["last_name"]}'.strip()
    return d


def update_booking(
    booking_id: int,
    *,
    first_name: str,
    last_name: str,
    contact: str,
    age_group: str,
    reg_type: str,
    db_path: str = DB_PATH
) -> bool:
    conn = get_db(db_path)
    cur = conn.execute(
        """
        UPDATE bookings
        SET first_name = ?, last_name = ?, contact = ?, age_group = ?, reg_type = ?
        WHERE id = ?
        """,
        (first_name, last_name, contact, age_group, reg_type, booking_id)
    )
    conn.commit()
    ok = cur.rowcount == 1
    conn.close()
    return ok


def delete_booking(booking_id: int, *, db_path: str = DB_PATH) -> bool:
    conn = get_db(db_path)
    cur = conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    conn.commit()
    ok = cur.rowcount == 1
    conn.close()
    return ok


def clear_bookings(*, db_path: str = DB_PATH) -> None:
    conn = get_db(db_path)
    conn.execute("DELETE FROM bookings")
    conn.commit()
    conn.close()
