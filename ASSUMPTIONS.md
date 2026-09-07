# ASSUMPTIONS

Decisions taken where SPEC.md left room, or where an M1 shortcut departs
from the eventual (M2+) shape. Each entry says what was assumed and why.

## M1 — szkielet end-to-end

- **First commit predates `.gitignore`.** START.md's step order ("`.gitignore`
  first, then `git init`") assumed a fresh repo, but `SPEC.md`/`START.md`
  were already committed before this session began. `.gitignore` was added
  as the first file of this session's work instead. No secrets, corpus, or
  DB files were present in that earlier commit, so nothing sensitive leaked.

- **`.gitignore` extended beyond the SPEC 9.1 minimum.** Added
  `__pycache__/`, `*.pyc`, `.venv/`, `.pytest_cache/`, `*.egg-info/` —
  standard Python/uv hygiene, not secrets-related, so keeping them out of
  the SPEC-mandated list didn't seem worth the noise it would otherwise add
  to every commit.

- **`profile.yaml` gained a `teaser` field** not listed in SPEC 4.2's field
  enumeration. SPEC 3.1 requires the author tile to show "1–2 zdania czego
  się spodziewać" and to be fully data-driven (no code changes to add an
  author), so that text has to live in the author's own directory. Added as
  `teaser: str` in `AuthorProfile`.

- **Settings persistence is browser-local, not a server-side config file.**
  SPEC 3.5 says the API key lives "w lokalnym pliku konfiguracyjnym" and
  MUST NOT reach the DB/logs/export. M1 has no DB or export yet, and building
  a settings-file read/write endpoint felt like scope beyond "adapter +
  drawer works". For M1, the base `Settings` still loads from `.env`/env
  vars (server-side), and drawer values are per-run overrides sent with each
  request and persisted only in the browser's `localStorage` for convenience
  across reloads. Revisit if/when a server-side settings file is wanted.

- **Only `diary serve` and `diary authors list` exist in the CLI.** SPEC
  section 9 lists `index`, `write`, `export`, `eval`, `backup` too, but
  those have nothing to operate on before M2/M3 (no DB, no index, no eval
  harness). Their modules exist as scope placeholders
  (`core/style/indexing.py`, `core/eval/harness.py`, `core/portfolio/export.py`,
  ...) with one-line comments; the CLI itself doesn't stub commands that
  would just say "not implemented".

- **UI language switching is not wired.** SPEC 5.4 treats `ui_language` and
  `story_language` as two separate settings. Only `story_language` affects
  anything in M1 (it feeds the prompt's `{story_lang}` layer); UI text is
  hardcoded Polish per START.md's instruction ("UI ... domyślnie po
  polsku"). `ui_language` exists as a `Settings` field for shape-stability
  but has no effect yet.

- **`prompts/narrator.md`'s leading `#` header lines and `<!-- -->` block are
  stripped by the builder, not sent to the model.** The file's own header
  comment says placeholders are filled by the builder and layer order MUST
  stay — but the `<!-- -->` block is dated documentation showing what
  `{safety_rules}` looks like under the detector/streak reinforcements (SPEC
  6.4/6.6), including a `{streak_shift}` placeholder that no M1 code ever
  supplies. Treated it as authoring notes for humans editing the template,
  stripped before `str.format()` — otherwise it would either raise
  `KeyError` or leak raw documentation text into the actual prompt.

- **Safety rules layer uses a fixed baseline text in M1.** SPEC 6.4's
  reinforcement variants only trigger via the input detector (6.2) or streak
  mode (6.6), neither of which exists yet (M2/M4). `DEFAULT_SAFETY_RULES` in
  `prompt_builder.py` is always the un-reinforced baseline.

- **Retrieval and world-state layers render as explicit Polish placeholder
  sentences** ("brak indeksu korpusu…", "brak zapisanego świata…") rather
  than being omitted from the prompt. This matches SPEC 4.4's "Brak indeksu
  → działa samo style card, UI to sygnalizuje" and keeps the template's
  layer positions stable once M2/M3 fill them with real content.

- **The five UI stages (SPEC 3.3) are all emitted every run**, even though
  "sprawdzam" (output filter, M2) and "zapisuję" (storage, M2) do no real
  work yet — they pass through instantly. Chosen over dropping stages so the
  UI's stage indicator doesn't need reshaping once M2 gives them substance.

- **`generate_structured` uses OpenAI's `json_object` response format**, not
  a per-provider structured-output feature (e.g. strict JSON schema mode).
  Not exercised by any M1 code path (no metadata call yet); implemented
  functionally rather than left as `NotImplementedError`, since the
  interface itself is supposed to be complete in M1 per SPEC 3.5, but its
  correctness against a real provider is unverified until M2 uses it.
