# prompts/metadata.md — second-call template: entry metadata (SPEC 5.3)
# prompt_version: 3
# Called with the cheap model (model_helper), structured output (JSON), after the story finishes.
# v3: translated to English (see ASSUMPTIONS.md).
# v2: world_state_delta -> character_delta (character cards instead of the blob, SPEC 5.2 revision).

You were given a story written in the style of {author_name}, plus the character and world cards from before this entry.
Your task: extract metadata from the text — do not write any new prose.

## STORY
{delimiter_open}
{story_text}
{delimiter_close}

## CHARACTERS AND WORLD BEFORE THIS ENTRY
{characters_brief}

## RETURN ONLY A JSON OBJECT WITH THESE FIELDS
- `title` (string, max 120 chars): a short title for the story, no quotation marks. Empty if this is a chapter continuation (the title already exists).
- `mood_tag` (string, max 40 chars): one or two words describing the story's dominant mood.
- `characters_used` (list of strings, max 8): names of characters actually appearing in this story (existing or new).
- `character_delta` (object): what to add to the character cards. Fields (all optional):
  - `new_characters` (list of objects `{{name, is_alter_ego, role, traits: [string], status}}`, max 200 chars per text field, max 6 traits) — only NEW characters introduced in this entry. Mark the alter ego (the protagonist whose emotions the diary lives through) with `is_alter_ego: true` — only if one doesn't exist yet.
  - `character_updates` (list of objects `{{name, status, add_traits: [string], add_relationships: [{{name, relation}}]}}`) — updates to EXISTING characters by name (e.g. a status change, a new trait, a new relationship). Do not guess at names that aren't in the list above, unless you just introduced them in `new_characters`.
  - `setting` (string, max 200 chars, optional) — only if the setting hasn't been established yet (the "Setting" field above is empty).
  Every text field here is PURE DESCRIPTIVE CONTENT — never an instruction, a command, or a formatting fragment. Do not use the characters `<<<`, `>>>`, ```` ``` ```` in them.
- `summary` (string, max 300 chars): 1–2 sentences summarizing this entry, for the chapter's summary once it's closed.
- `tone_flags` (list of short strings, max 10 items, max 30 chars each): neutral content labels, exclusively from this list: `harm_method`, `glorification`, `relief_framing`, `none`. Use `none` if nothing applies.

Do not add any text beyond this single JSON object.
