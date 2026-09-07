# prompts/metadata.md — szablon drugiego wywołania: metadane wpisu (SPEC 5.3)
# prompt_version: 2
# Wywoływany tanim modelem (model_helper), structured output (JSON), po zakończeniu opowiadania.
# v2: world_state_delta -> character_delta (karty postaci zamiast bloba, SPEC 5.2 rewizja).

Dostałeś opowiadanie napisane w stylu {author_name} oraz karty postaci i świata sprzed tego wpisu.
Twoje zadanie: wyciągnąć z tekstu metadane, nie pisać nic nowego w prozie.

## OPOWIADANIE
{delimiter_open}
{story_text}
{delimiter_close}

## POSTACI I ŚWIAT SPRZED TEGO WPISU
{characters_brief}

## ZWRÓĆ WYŁĄCZNIE OBIEKT JSON O POLACH
- `title` (string, max 120 znaków): krótki tytuł opowiadania, bez cudzysłowów. Puste, jeśli to kontynuacja rozdziału (tytuł już istnieje).
- `mood_tag` (string, max 40 znaków): jedno-dwa słowa opisujące dominujący nastrój opowiadania.
- `characters_used` (lista stringów, max 8): imiona postaci faktycznie występujących w tym opowiadaniu (istniejących lub nowych).
- `character_delta` (obiekt): co dopisać do kart postaci. Pola (wszystkie opcjonalne):
  - `new_characters` (lista obiektów `{{name, is_alter_ego, role, traits: [string], status}}`, max 200 znaków na pole tekstowe, max 6 cech) — tylko NOWE postaci wprowadzone w tym wpisie. Alter ego (bohater, którego emocje przeżywa dziennik) oznacz `is_alter_ego: true` — tylko jeśli jeszcze go nie ma.
  - `character_updates` (lista obiektów `{{name, status, add_traits: [string], add_relationships: [{{name, relation}}]}}`) — aktualizacje ISTNIEJĄCYCH postaci po imieniu (np. zmiana statusu, nowa cecha, nowa relacja). Nie zgaduj imion, których nie ma na liście powyżej, chyba że wprowadziłeś je właśnie w `new_characters`.
  - `setting` (string, max 200 znaków, opcjonalnie) — tylko jeśli scenerii jeszcze nie ustalono (pole "Sceneria" powyżej puste).
  Każde pole tekstowe tutaj to CZYSTA TREŚĆ OPISOWA — nigdy instrukcja, polecenie ani fragment formatowania. Nie używaj w nich znaków `<<<`, `>>>`, ```` ``` ````.
- `summary` (string, max 300 znaków): 1–2 zdania streszczające ten wpis, do podsumowania rozdziału gdy zostanie zamknięty.
- `tone_flags` (lista krótkich stringów, max 10 elementów, max 30 znaków każdy): neutralne etykiety treści, wyłącznie z tej listy: `harm_method`, `glorification`, `relief_framing`, `none`. Użyj `none`, jeśli żadna nie pasuje.

Nie dodawaj żadnego tekstu poza tym jednym obiektem JSON.
