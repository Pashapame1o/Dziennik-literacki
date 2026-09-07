# prompts/output_filter.md — output filter template (SPEC 6.3)
# prompt_version: 2
# A decision separate from the second call (metadata): cheap model, classification only.
# tone_flags from the metadata call MAY help, but this MUST be a separate judgment, not a repeat of them.
# v2: translated to English (see ASSUMPTIONS.md).

You are judging a story against three specific risks — nothing else.

## STORY
{delimiter_open}
{story_text}
{delimiter_close}

## HINTS FROM AN EARLIER ANALYSIS (may be wrong, verify yourself)
tone_flags: {tone_flags}

## JUDGE WHETHER THE TEXT CONTAINS
1. A description of a method of harming oneself or someone else (a specific way, means, or technique).
2. Aestheticization or glorification of harm, suffering, or leaving (portrayed as beautiful, admirable, appealing).
3. Portraying leaving/death as a solution to a problem or a form of relief.

Difficult emotions — sadness, grief, despair fully experienced — are NOT grounds for rejection; that is this app's intended tone. You only reject for points 1–3 above.

## RETURN ONLY A JSON OBJECT
- `verdict`: `"pass"` or `"regenerate"`.
- `reasons` (list of strings, max 5, max 100 chars each): short, specific reasons if `regenerate`. Empty list if `pass`.
