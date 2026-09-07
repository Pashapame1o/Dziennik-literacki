-- Replaces the M2 world_states blob with compact per-character records,
-- chapter grouping, and a small per-author world_meta row. No real user
-- data exists yet, so we cut cleanly rather than carry dead schema forward
-- (see ASSUMPTIONS.md "M2.5" for why the blob didn't support continuation).

DROP TABLE IF EXISTS world_states;

CREATE TABLE world_meta (
    author_slug TEXT PRIMARY KEY,
    setting TEXT NOT NULL DEFAULT '',
    era TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_slug TEXT NOT NULL,
    name TEXT NOT NULL,
    is_alter_ego INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT '',
    traits TEXT NOT NULL DEFAULT '[]',         -- JSON list[str], short phrases
    relationships TEXT NOT NULL DEFAULT '[]',  -- JSON list[{"name": str, "relation": str}]
    status TEXT NOT NULL DEFAULT '',           -- e.g. "żywy", "martwy", "nieobecny"
    locked INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,                          -- soft-archive; reserved for M4 compaction
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (author_slug, name)
);

CREATE INDEX idx_characters_author_slug ON characters(author_slug);

CREATE TABLE chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_slug TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    title TEXT,
    summary TEXT,               -- filled on close: a few sentences, not full text
    created_at TEXT NOT NULL,
    closed_at TEXT
);

CREATE INDEX idx_chapters_author_slug ON chapters(author_slug);

ALTER TABLE entries ADD COLUMN chapter_id INTEGER REFERENCES chapters(id);
ALTER TABLE entries DROP COLUMN world_state_version;
