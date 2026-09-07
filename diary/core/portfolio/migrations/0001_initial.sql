-- SPEC 7.1 — initial schema. schema_version bookkeeping itself is bootstrapped
-- by storage.py before migrations run, not by a migration file (chicken/egg:
-- the runner needs the tracking table to exist before it can consult it).

CREATE TABLE entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,          -- UTC, ISO 8601
    created_at_tz TEXT NOT NULL,       -- IANA zone the entry was made in
    type TEXT NOT NULL CHECK (type IN ('story', 'summary_chapter')),
    author_slug TEXT NOT NULL,
    parent_entry_id INTEGER REFERENCES entries(id),
    mood_inputs TEXT,                  -- JSON; NULL for summary_chapter
    title TEXT,
    story_text TEXT NOT NULL,
    story_lang TEXT NOT NULL,
    mood_tag TEXT,
    summary TEXT,
    characters_used TEXT,              -- JSON list[str]
    world_state_version INTEGER,
    safety_input_flag INTEGER NOT NULL DEFAULT 0,
    safety_output_result TEXT NOT NULL DEFAULT 'pass',  -- pass | regenerated | fallback
    streak_mode INTEGER NOT NULL DEFAULT 0,
    model_used TEXT NOT NULL,
    prompt_version INTEGER NOT NULL,
    style_profile_version INTEGER NOT NULL,
    retrieval_chunks TEXT,             -- JSON; unused until M3
    deleted_at TEXT
);

CREATE INDEX idx_entries_author_slug ON entries(author_slug);
CREATE INDEX idx_entries_created_at ON entries(created_at);

CREATE TABLE world_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_slug TEXT NOT NULL,
    version INTEGER NOT NULL,
    canon TEXT NOT NULL,               -- JSON
    recent_threads TEXT NOT NULL,      -- JSON
    created_at TEXT NOT NULL,
    UNIQUE (author_slug, version)
);

CREATE TABLE author_index_meta (
    author_slug TEXT PRIMARY KEY,
    files TEXT,                        -- JSON list[str]; unused until M3
    chunk_count INTEGER NOT NULL DEFAULT 0,
    embed_model TEXT,
    tagged INTEGER NOT NULL DEFAULT 0,
    last_indexed_at TEXT
);

CREATE TABLE safety_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER REFERENCES entries(id),
    stage TEXT NOT NULL CHECK (stage IN ('input_detector', 'output_filter')),
    verdict TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- No entry content ever lands in this table (SPEC 6.3): verdict is a short
-- label ('triggered', 'pass', 'regenerated', 'fallback', ...), not text.

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Key-value only; API keys/secrets MUST NEVER be written here (SPEC 7.1).
