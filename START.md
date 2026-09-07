# Wiadomość startowa dla agenta (wklej jako pierwszą wiadomość; `SPEC.md` i `prompts/narrator.md` muszą być już w repo)

Jesteś doświadczonym inżynierem full-stack (Python/FastAPI + lekki frontend) z praktyką w aplikacjach opartych o LLM. Budujesz aplikację do użytku osobistego: **dziennik emocji zamieniany w opowiadanie w stylu klasycznego autora**. Użytkownik wybiera autora, wypełnia krótki ustrukturyzowany formularz o dzisiejszym stanie, a model — w stylu tego autora — sam wymyśla świat, bohaterów i pisze opowiadanie, w którym te emocje przeżywa postać literacka. Architektura wzorowana na hr-breaker (FastAPI + Alpine.js z CDN, SSE, settings drawer z per-run overrides, BYO model i klucz).

Pełna specyfikacja jest w `SPEC.md` — odwołuj się do niej po numerach sekcji. Szablon promptu narratora jest w `prompts/narrator.md` i ma być wczytywany z pliku, nie wpisany w kod.

## Zasady pracy
- Najpierw przedstaw krótki plan (struktura repo, kolejność kroków w tym milestone'ie), potem implementuj.
- Niejasność → przyjmij rozsądne założenie, zapisz je w `ASSUMPTIONS.md`, idź dalej.
- Kod, nazwy, komentarze po angielsku; UI i teksty promptów domyślnie po polsku.
- Testy dla logiki niezależnej od LLM (budowanie promptu, parsowanie, walidacja); adapter LLM w testach mockowany.
- Słowa MUST / SHOULD / MAY w `SPEC.md` mają dosłowne znaczenie.
- Sekcja 10 `SPEC.md` (Non-goals) obowiązuje od pierwszego commita: brak kont, Dockera, chmury, build stepu, zewnętrznego vector store, alembica, wolnego pola tekstowego.

## Zakres tej iteracji: wyłącznie Milestone 1 (SPEC sekcja 11, M1)
Zbuduj szkielet end-to-end:
- **Pierwszy krok, przed czymkolwiek innym**: utwórz `.gitignore` dokładnie wg SPEC 9.1. Dopiero potem `git init` / pierwszy commit.
- `uv`, Python 3.12, FastAPI, `sse-starlette`, `pydantic-settings`, `typer`; struktura katalogów z SPEC 9 (puste moduły tam, gdzie zakres jeszcze nie sięga).
- Settings z env + context manager per-run overrides; settings drawer w UI (provider, model, klucz, temperatura, długość).
- Własny interfejs adaptera LLM (`generate_stream`, `generate_structured`, `embed`) z jedną implementacją (OpenAI-compatible) i mockiem do testów.
- Jeden autor (`authors/dostoevsky/profile.yaml`, SPEC 4.2) działający na samym style card — bez korpusu i bez RAG.
- Ekrany 1–3 (SPEC 3.1–3.3): wybór autora z katalogu `authors/`, formularz z SPEC 3.2 (walencja, energia, chipy, pytania tak/nie z `question_id`, słowa kluczowe, opcjonalne zdanie z limitami egzekwowanymi serwerowo), streamowana proza z etapami.
- Prompt builder składający warstwy z SPEC 5.1 na podstawie `prompts/narrator.md`; input jako JSON w ograniczniku z losowym tokenem per request; `safety_rules` na razie w wersji domyślnej.
- Czytelna obsługa błędnego klucza bez utraty formularza.

Poza zakresem tej iteracji: baza danych, world state, drugie wywołanie na metadane, detektor i filtr bezpieczeństwa, RAG, portfolio, eval (SPEC sekcje 4.3–4.5, 5.2–5.3, 6, 7, 8). Nie implementuj ich „przy okazji” — zostaw jasne miejsca w strukturze.

## Definition of Done dla M1
1. `uv sync && uv run diary serve` uruchamia UI; wybór autora → formularz → streamowana proza.
2. Zmiana modelu/klucza w drawerze działa bez restartu.
3. Output to wyłącznie proza — test na mocku sprawdza brak tytułu/nagłówka.
4. Test jednostkowy buildera potwierdza: input jako JSON w losowym ograniczniku, wszystkie warstwy w kolejności z SPEC 5.1.
5. Błędny klucz daje czytelny komunikat, formularz nie znika.

Na koniec: podsumowanie co działa, co odłożone, i aktualizacja `ASSUMPTIONS.md`.
