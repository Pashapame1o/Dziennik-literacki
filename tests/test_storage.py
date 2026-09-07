"""SQLite migrations + storage helpers (SPEC 7.1, revised in "M2.5" —
world_states replaced by characters/chapters/world_meta)."""

from __future__ import annotations

import pytest

from diary.core.portfolio import storage


@pytest.fixture
def conn():
    conn = storage.get_connection(":memory:")
    yield conn
    conn.close()


def test_migrations_create_all_expected_tables(conn):
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    for expected in (
        "entries", "characters", "chapters", "world_meta",
        "author_index_meta", "safety_events", "settings", "schema_version",
    ):
        assert expected in tables
    assert "world_states" not in tables  # replaced, not kept alongside


def test_schema_version_records_both_migrations(conn):
    versions = [row["version"] for row in conn.execute("SELECT version FROM schema_version")]
    assert versions == [1, 2]


def test_applying_migrations_twice_is_a_no_op(tmp_path):
    db_path = str(tmp_path / "diary.db")
    conn1 = storage.get_connection(db_path)
    conn1.close()

    # second open on the same file must not re-run 0001/0002 (would fail on
    # "table already exists" if the version check didn't work)
    conn2 = storage.get_connection(db_path)
    versions = [row["version"] for row in conn2.execute("SELECT version FROM schema_version")]
    assert versions == [1, 2]
    conn2.close()


def test_entries_has_chapter_id_and_not_world_state_version(conn):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(entries)")}
    assert "chapter_id" in columns
    assert "world_state_version" not in columns


def test_insert_and_get_entry_roundtrip(conn):
    chapter_id = storage.insert_chapter(conn, "dostoevsky")
    entry_id = storage.insert_entry(
        conn,
        type="story",
        author_slug="dostoevsky",
        story_text="Rano padał deszcz.",
        story_lang="polsku",
        model_used="gpt-4o-mini",
        prompt_version=3,
        style_profile_version=1,
        chapter_id=chapter_id,
        mood_inputs={"valence": -2, "energy": 3},
        title="Deszcz",
        characters_used=["Arkadij"],
        safety_input_flag=True,
        safety_output_result="regenerated",
    )

    row = storage.get_entry(conn, entry_id)
    assert row is not None
    data = storage.entry_to_dict(row)
    assert data["story_text"] == "Rano padał deszcz."
    assert data["mood_inputs"] == {"valence": -2, "energy": 3}
    assert data["characters_used"] == ["Arkadij"]
    assert data["safety_input_flag"] is True
    assert data["safety_output_result"] == "regenerated"
    assert data["chapter_id"] == chapter_id
    assert data["deleted_at"] is None


def test_get_entry_excludes_soft_deleted(conn):
    entry_id = storage.insert_entry(
        conn, type="story", author_slug="dostoevsky", story_text="x", story_lang="polsku",
        model_used="m", prompt_version=1, style_profile_version=1,
    )
    conn.execute("UPDATE entries SET deleted_at = ? WHERE id = ?", ("2026-01-01T00:00:00Z", entry_id))
    conn.commit()

    assert storage.get_entry(conn, entry_id) is None


def test_list_entries_for_author_orders_newest_first(conn):
    first = storage.insert_entry(
        conn, type="story", author_slug="dostoevsky", story_text="pierwszy", story_lang="polsku",
        model_used="m", prompt_version=1, style_profile_version=1,
    )
    second = storage.insert_entry(
        conn, type="story", author_slug="dostoevsky", story_text="drugi", story_lang="polsku",
        model_used="m", prompt_version=1, style_profile_version=1,
    )
    others = storage.insert_entry(
        conn, type="story", author_slug="tolstoy", story_text="inny autor", story_lang="polsku",
        model_used="m", prompt_version=1, style_profile_version=1,
    )

    rows = storage.list_entries_for_author(conn, "dostoevsky")
    assert [r["id"] for r in rows] == [second, first]
    assert others not in [r["id"] for r in rows]


def test_safety_event_never_stores_content(conn):
    entry_id = storage.insert_entry(
        conn, type="story", author_slug="dostoevsky", story_text="x", story_lang="polsku",
        model_used="m", prompt_version=1, style_profile_version=1,
    )
    storage.insert_safety_event(conn, entry_id=entry_id, stage="output_filter", verdict="regenerated")

    row = conn.execute("SELECT * FROM safety_events WHERE entry_id = ?", (entry_id,)).fetchone()
    assert set(row.keys()) == {"id", "entry_id", "stage", "verdict", "created_at"}
    assert row["verdict"] == "regenerated"


def test_count_entries_for_author(conn):
    assert storage.count_entries_for_author(conn, "dostoevsky") == 0
    storage.insert_entry(
        conn, type="story", author_slug="dostoevsky", story_text="x", story_lang="polsku",
        model_used="m", prompt_version=1, style_profile_version=1,
    )
    assert storage.count_entries_for_author(conn, "dostoevsky") == 1


# --- characters --------------------------------------------------------


def _card(name, **overrides):
    card = {"name": name, "is_alter_ego": False, "role": "", "traits": [], "relationships": [], "status": "", "locked": False}
    card.update(overrides)
    return card


def test_replace_characters_inserts_new_cards(conn):
    storage.replace_characters(conn, "dostoevsky", [_card("Arkadij", is_alter_ego=True, traits=["dumny"])])
    rows = storage.list_characters(conn, "dostoevsky")
    assert len(rows) == 1
    data = storage.character_row_to_dict(rows[0])
    assert data["name"] == "Arkadij"
    assert data["is_alter_ego"] is True
    assert data["traits"] == ["dumny"]


def test_replace_characters_upserts_existing_card_by_name(conn):
    storage.replace_characters(conn, "dostoevsky", [_card("Arkadij", status="żywy")])
    storage.replace_characters(conn, "dostoevsky", [_card("Arkadij", status="martwy")])

    rows = storage.list_characters(conn, "dostoevsky")
    assert len(rows) == 1  # not duplicated
    assert storage.character_row_to_dict(rows[0])["status"] == "martwy"


def test_replace_characters_removes_cards_not_in_the_new_set(conn):
    storage.replace_characters(conn, "dostoevsky", [_card("Arkadij"), _card("Ludmiła")])
    storage.replace_characters(conn, "dostoevsky", [_card("Arkadij")])  # Ludmiła dropped

    names = {row["name"] for row in storage.list_characters(conn, "dostoevsky")}
    assert names == {"Arkadij"}


def test_characters_are_scoped_per_author(conn):
    storage.replace_characters(conn, "dostoevsky", [_card("Arkadij")])
    storage.replace_characters(conn, "tolstoy", [_card("Piotr")])

    assert {r["name"] for r in storage.list_characters(conn, "dostoevsky")} == {"Arkadij"}
    assert {r["name"] for r in storage.list_characters(conn, "tolstoy")} == {"Piotr"}


def test_relationships_roundtrip_as_json(conn):
    storage.replace_characters(
        conn, "dostoevsky",
        [_card("Arkadij", relationships=[{"name": "Ludmiła", "relation": "lokator"}])],
    )
    data = storage.character_row_to_dict(storage.list_characters(conn, "dostoevsky")[0])
    assert data["relationships"] == [{"name": "Ludmiła", "relation": "lokator"}]


# --- world_meta ----------------------------------------------------------


def test_world_meta_absent_by_default(conn):
    assert storage.get_world_meta(conn, "dostoevsky") is None


def test_world_meta_upsert_and_read(conn):
    storage.upsert_world_meta(conn, "dostoevsky", setting="Petersburg, jesień", era="XIX wiek")
    row = storage.get_world_meta(conn, "dostoevsky")
    assert row["setting"] == "Petersburg, jesień"
    assert row["era"] == "XIX wiek"

    storage.upsert_world_meta(conn, "dostoevsky", setting="Inne miejsce")
    updated = storage.get_world_meta(conn, "dostoevsky")
    assert updated["setting"] == "Inne miejsce"  # upsert overwrites, caller enforces "first wins"


# --- chapters (book interface) ----------------------------------------------


def test_insert_chapter_starts_open_with_no_title_or_summary(conn):
    chapter_id = storage.insert_chapter(conn, "dostoevsky")
    chapter = storage.get_chapter(conn, chapter_id)
    assert chapter["status"] == "open"
    assert chapter["title"] is None
    assert chapter["summary"] is None
    assert chapter["closed_at"] is None


def test_set_chapter_title_if_unset_only_sets_once(conn):
    chapter_id = storage.insert_chapter(conn, "dostoevsky")
    storage.set_chapter_title_if_unset(conn, chapter_id, "Deszcz")
    storage.set_chapter_title_if_unset(conn, chapter_id, "Inny tytuł")

    assert storage.get_chapter(conn, chapter_id)["title"] == "Deszcz"


def test_close_chapter_sets_status_summary_and_closed_at(conn):
    chapter_id = storage.insert_chapter(conn, "dostoevsky")
    storage.close_chapter(conn, chapter_id, summary="Arkadij poznaje Ludmiłę.")

    chapter = storage.get_chapter(conn, chapter_id)
    assert chapter["status"] == "closed"
    assert chapter["summary"] == "Arkadij poznaje Ludmiłę."
    assert chapter["closed_at"] is not None


def test_list_entries_for_chapter_orders_by_id(conn):
    chapter_id = storage.insert_chapter(conn, "dostoevsky")
    first = storage.insert_entry(
        conn, type="story", author_slug="dostoevsky", story_text="pierwszy", story_lang="polsku",
        model_used="m", prompt_version=1, style_profile_version=1, chapter_id=chapter_id,
    )
    second = storage.insert_entry(
        conn, type="story", author_slug="dostoevsky", story_text="drugi", story_lang="polsku",
        model_used="m", prompt_version=1, style_profile_version=1, chapter_id=chapter_id,
    )
    rows = storage.list_entries_for_chapter(conn, chapter_id)
    assert [r["id"] for r in rows] == [first, second]


def test_list_chapters_for_author_scoped_and_ordered(conn):
    c1 = storage.insert_chapter(conn, "dostoevsky")
    storage.insert_chapter(conn, "tolstoy")
    c2 = storage.insert_chapter(conn, "dostoevsky")

    rows = storage.list_chapters_for_author(conn, "dostoevsky")
    assert [r["id"] for r in rows] == [c1, c2]
