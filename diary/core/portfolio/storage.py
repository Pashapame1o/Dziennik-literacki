"""SQLite storage for entries/characters/chapters/etc. (SPEC 7.1).

Plain `sqlite3` (stdlib), numbered SQL migration files + a `schema_version`
table — no ORM, no alembic (SPEC 9/10). This is a personal, single-user,
single-process app, so a straightforward blocking connection per call is
enough; there is no concurrent load to justify a connection pool or async
driver.

This module deals only in plain dicts/JSON, never domain objects
(`CharacterCard`, `WorldMeta`, ...) — callers (routes.py) convert between
domain objects and the primitive shapes here, keeping storage free of a
dependency on `diary.core.story`.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )


def apply_migrations(conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> None:
    _ensure_schema_version_table(conn)
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_version")}
    for path in sorted(migrations_dir.glob("*.sql")):
        version = int(path.name.split("_", 1)[0])
        if version in applied:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)", (version, _now_iso())
        )
    conn.commit()


def get_connection(db_path: str) -> sqlite3.Connection:
    """Opens a connection with migrations applied. `:memory:` is fine for tests."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)
    return conn


# --- entries ---------------------------------------------------------------


def insert_entry(
    conn: sqlite3.Connection,
    *,
    type: str,
    author_slug: str,
    story_text: str,
    story_lang: str,
    model_used: str,
    prompt_version: int,
    style_profile_version: int,
    chapter_id: int | None = None,
    parent_entry_id: int | None = None,
    mood_inputs: dict[str, Any] | None = None,
    title: str | None = None,
    mood_tag: str | None = None,
    summary: str | None = None,
    characters_used: list[str] | None = None,
    safety_input_flag: bool = False,
    safety_output_result: str = "pass",
    streak_mode: bool = False,
    retrieval_chunks: list[Any] | None = None,
    created_at_tz: str = "UTC",
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO entries (
            created_at, created_at_tz, type, author_slug, parent_entry_id, chapter_id,
            mood_inputs, title, story_text, story_lang, mood_tag, summary,
            characters_used, safety_input_flag,
            safety_output_result, streak_mode, model_used, prompt_version,
            style_profile_version, retrieval_chunks
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _now_iso(),
            created_at_tz,
            type,
            author_slug,
            parent_entry_id,
            chapter_id,
            json.dumps(mood_inputs, ensure_ascii=False) if mood_inputs is not None else None,
            title,
            story_text,
            story_lang,
            mood_tag,
            summary,
            json.dumps(characters_used, ensure_ascii=False) if characters_used is not None else None,
            int(safety_input_flag),
            safety_output_result,
            int(streak_mode),
            model_used,
            prompt_version,
            style_profile_version,
            json.dumps(retrieval_chunks, ensure_ascii=False) if retrieval_chunks is not None else None,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_entry(conn: sqlite3.Connection, entry_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM entries WHERE id = ? AND deleted_at IS NULL", (entry_id,)).fetchone()


def list_entries_for_author(
    conn: sqlite3.Connection, author_slug: str, *, limit: int = 50
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM entries WHERE author_slug = ? AND deleted_at IS NULL "
        "ORDER BY created_at DESC LIMIT ?",
        (author_slug, limit),
    ).fetchall()


def list_entries_for_chapter(conn: sqlite3.Connection, chapter_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM entries WHERE chapter_id = ? AND deleted_at IS NULL ORDER BY id ASC",
        (chapter_id,),
    ).fetchall()


_JSON_ENTRY_COLUMNS = ("mood_inputs", "characters_used", "retrieval_chunks")


def entry_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Row -> dict with the JSON columns decoded, for callers that want Python
    values (API responses, debug panel) instead of raw sqlite3.Row/JSON text."""
    data = dict(row)
    for col in _JSON_ENTRY_COLUMNS:
        if data.get(col) is not None:
            data[col] = json.loads(data[col])
    data["safety_input_flag"] = bool(data["safety_input_flag"])
    data["streak_mode"] = bool(data["streak_mode"])
    return data


def count_entries_for_author(conn: sqlite3.Connection, author_slug: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM entries WHERE author_slug = ? AND deleted_at IS NULL", (author_slug,)
    ).fetchone()
    return row["n"]


# --- characters (SPEC 5.2, revised — see ASSUMPTIONS.md "M2.5") ------------


def list_characters(conn: sqlite3.Connection, author_slug: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM characters WHERE author_slug = ? AND archived_at IS NULL ORDER BY id ASC",
        (author_slug,),
    ).fetchall()


def replace_characters(conn: sqlite3.Connection, author_slug: str, characters: list[dict[str, Any]]) -> None:
    """Upserts the given cards by (author_slug, name) and removes any active
    card not present in `characters` — the caller always passes the full,
    already-merged active set (existing + delta applied), so this keeps
    storage consistent with whatever the caller decided, without storage.py
    needing to know the merge rules itself."""
    now = _now_iso()
    incoming_names = {c["name"] for c in characters}
    existing_names = {row["name"] for row in list_characters(conn, author_slug)}

    for card in characters:
        conn.execute(
            """
            INSERT INTO characters (
                author_slug, name, is_alter_ego, role, traits, relationships, status, locked,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(author_slug, name) DO UPDATE SET
                is_alter_ego = excluded.is_alter_ego,
                role = excluded.role,
                traits = excluded.traits,
                relationships = excluded.relationships,
                status = excluded.status,
                locked = excluded.locked,
                updated_at = excluded.updated_at
            """,
            (
                author_slug,
                card["name"],
                int(card.get("is_alter_ego", False)),
                card.get("role", ""),
                json.dumps(card.get("traits", []), ensure_ascii=False),
                json.dumps(card.get("relationships", []), ensure_ascii=False),
                card.get("status", ""),
                int(card.get("locked", False)),
                now,
                now,
            ),
        )

    for stale_name in existing_names - incoming_names:
        conn.execute("DELETE FROM characters WHERE author_slug = ? AND name = ?", (author_slug, stale_name))

    conn.commit()


def character_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["traits"] = json.loads(data["traits"])
    data["relationships"] = json.loads(data["relationships"])
    data["is_alter_ego"] = bool(data["is_alter_ego"])
    data["locked"] = bool(data["locked"])
    return data


# --- world_meta --------------------------------------------------------


def get_world_meta(conn: sqlite3.Connection, author_slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM world_meta WHERE author_slug = ?", (author_slug,)).fetchone()


def upsert_world_meta(conn: sqlite3.Connection, author_slug: str, *, setting: str, era: str = "") -> None:
    conn.execute(
        """
        INSERT INTO world_meta (author_slug, setting, era, updated_at) VALUES (?, ?, ?, ?)
        ON CONFLICT(author_slug) DO UPDATE SET setting = excluded.setting, era = excluded.era,
            updated_at = excluded.updated_at
        """,
        (author_slug, setting, era, _now_iso()),
    )
    conn.commit()


# --- chapters (book interface) ----------------------------------------------


def insert_chapter(conn: sqlite3.Connection, author_slug: str) -> int:
    cursor = conn.execute(
        "INSERT INTO chapters (author_slug, status, created_at) VALUES (?, 'open', ?)",
        (author_slug, _now_iso()),
    )
    conn.commit()
    return cursor.lastrowid


def get_chapter(conn: sqlite3.Connection, chapter_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone()


def set_chapter_title_if_unset(conn: sqlite3.Connection, chapter_id: int, title: str) -> None:
    if not title:
        return
    conn.execute("UPDATE chapters SET title = ? WHERE id = ? AND title IS NULL", (title, chapter_id))
    conn.commit()


def close_chapter(conn: sqlite3.Connection, chapter_id: int, *, summary: str) -> None:
    conn.execute(
        "UPDATE chapters SET status = 'closed', summary = ?, closed_at = ? WHERE id = ?",
        (summary, _now_iso(), chapter_id),
    )
    conn.commit()


def list_chapters_for_author(conn: sqlite3.Connection, author_slug: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM chapters WHERE author_slug = ? ORDER BY created_at ASC", (author_slug,)
    ).fetchall()


# --- safety_events -----------------------------------------------------


def insert_safety_event(conn: sqlite3.Connection, *, entry_id: int | None, stage: str, verdict: str) -> int:
    cursor = conn.execute(
        "INSERT INTO safety_events (entry_id, stage, verdict, created_at) VALUES (?, ?, ?, ?)",
        (entry_id, stage, verdict, _now_iso()),
    )
    conn.commit()
    return cursor.lastrowid
