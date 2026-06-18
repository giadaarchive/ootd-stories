#!/usr/bin/env python3
"""
Corrections database — SQLite store that remembers user decisions.

Two learning modes:
  1. Exact image (SHA256 hash match) → skip AI entirely, replay prior decisions
  2. Item type + colour → boost previously-approved items to top of candidate list

Schema:
  corrections  — one row per approved/changed item decision
  image_cache  — maps image hash → list of item decisions (for mode 1 replay)
"""

import sqlite3, hashlib, json, time
from pathlib import Path

DB_PATH = Path(__file__).parent / "corrections.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS corrections (
                id                  INTEGER PRIMARY KEY,
                image_hash          TEXT NOT NULL,
                item_type           TEXT NOT NULL,
                item_colour         TEXT,
                visual_description  TEXT,
                ai_top_id           TEXT,
                ai_top_name         TEXT,
                correct_id          TEXT NOT NULL,
                correct_name        TEXT NOT NULL,
                wear_date           TEXT,
                ts                  REAL DEFAULT (unixepoch())
            );

            CREATE INDEX IF NOT EXISTS idx_type_colour
                ON corrections(item_type, item_colour);
            CREATE INDEX IF NOT EXISTS idx_image_hash
                ON corrections(image_hash);
            CREATE INDEX IF NOT EXISTS idx_correct_id
                ON corrections(correct_id);

            CREATE TABLE IF NOT EXISTS image_sessions (
                image_hash  TEXT NOT NULL,
                wear_date   TEXT,
                decisions   TEXT NOT NULL,  -- JSON list of {item_type, correct_id, correct_name}
                ts          REAL DEFAULT (unixepoch()),
                PRIMARY KEY (image_hash, wear_date)
            );
        """)


def image_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


# ── Write ─────────────────────────────────────────────────────────────────────

def save_decisions(
    img_hash: str,
    wear_date: str,
    decisions: list[dict],       # [{item_type, item_colour, visual_description, ai_top_id, ai_top_name, correct_id, correct_name}]
):
    """
    Persist user decisions after approval.
    decisions is the merged list of all approved items for this session.
    """
    init()
    session_decisions = []
    with _conn() as c:
        for d in decisions:
            c.execute("""
                INSERT INTO corrections
                    (image_hash, item_type, item_colour, visual_description,
                     ai_top_id, ai_top_name, correct_id, correct_name, wear_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                img_hash,
                d.get("item_type", ""),
                d.get("item_colour", ""),
                d.get("visual_description", ""),
                d.get("ai_top_id"),
                d.get("ai_top_name"),
                d["correct_id"],
                d["correct_name"],
                wear_date,
            ))
            session_decisions.append({
                "item_type": d.get("item_type", ""),
                "correct_id": d["correct_id"],
                "correct_name": d["correct_name"],
            })

        c.execute("""
            INSERT OR REPLACE INTO image_sessions (image_hash, wear_date, decisions)
            VALUES (?, ?, ?)
        """, (img_hash, wear_date, json.dumps(session_decisions)))


# ── Read ──────────────────────────────────────────────────────────────────────

def lookup_image(img_hash: str) -> list[dict] | None:
    """
    If we've seen this exact image before, return the saved decisions.
    Returns list of {item_type, correct_id, correct_name} or None.
    """
    init()
    with _conn() as c:
        row = c.execute(
            "SELECT decisions FROM image_sessions WHERE image_hash = ? ORDER BY ts DESC LIMIT 1",
            (img_hash,)
        ).fetchone()
    if row:
        return json.loads(row["decisions"])
    return None


def lookup_type_colour(item_type: str, item_colour: str, limit: int = 5) -> list[dict]:
    """
    Find previously-approved items for a given type+colour combination.
    Returns list of {correct_id, correct_name, count} sorted by frequency.
    Used to inject prior knowledge into candidate ranking.
    """
    init()
    type_lower = item_type.lower()
    colour_lower = item_colour.lower() if item_colour else ""

    with _conn() as c:
        # Exact type + colour match first
        rows = c.execute("""
            SELECT correct_id, correct_name, COUNT(*) as cnt
            FROM corrections
            WHERE lower(item_type) LIKE ? AND lower(item_colour) LIKE ?
            GROUP BY correct_id
            ORDER BY cnt DESC
            LIMIT ?
        """, (f"%{type_lower}%", f"%{colour_lower}%", limit)).fetchall()

        if not rows and type_lower:
            # Fall back to type-only match
            rows = c.execute("""
                SELECT correct_id, correct_name, COUNT(*) as cnt
                FROM corrections
                WHERE lower(item_type) LIKE ?
                GROUP BY correct_id
                ORDER BY cnt DESC
                LIMIT ?
            """, (f"%{type_lower}%", limit)).fetchall()

    return [{"correct_id": r["correct_id"], "correct_name": r["correct_name"], "count": r["cnt"]} for r in rows]


def correction_was_made(img_hash: str, ai_top_id: str, correct_id: str) -> bool:
    """True if user corrected AI's suggestion to a different item."""
    return ai_top_id != correct_id


def stats() -> dict:
    """Return basic stats on the corrections DB."""
    init()
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
        images = c.execute("SELECT COUNT(*) FROM image_sessions").fetchone()[0]
        corrected = c.execute(
            "SELECT COUNT(*) FROM corrections WHERE ai_top_id != correct_id AND ai_top_id IS NOT NULL"
        ).fetchone()[0]
    return {"total_decisions": total, "unique_images": images, "corrections": corrected}


if __name__ == "__main__":
    init()
    print("DB initialised at", DB_PATH)
    print("Stats:", stats())
