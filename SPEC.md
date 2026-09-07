# SPEC — „Dziennik literacki” (v2)

Dziennik emocji zamieniany w opowiadanie w stylu klasycznego autora. Aplikacja do użytku osobistego, każdy użytkownik podpina własny model i klucz API.

Słownictwo wymagań: **MUST** = twarde wymaganie, **SHOULD** = domyślne, odstępstwo wymaga zapisu w `ASSUMPTIONS.md`, **MAY** = opcjonalne.

---

## 1. Inspiracja architektoniczna

Punkt wyjścia: **hr-breaker** (github.com/btseytlin/hr-breaker) — CV + oferta pracy → zoptymalizowane CV przez LLM. Przenosimy mechanikę, nie domenę:

- FastAPI + Alpine.js jako SPA z CDN, serwowane statycznie, zero build.
- Streaming wyniku i etapów przez SSE.
- Settings drawer z nadpisaniami per-run (provider, model, klucz, parametry) przez context manager nakładający env overrides.
- Pickery oparte o katalogi na dysku (u nas: autorzy).
- Tryb językowy: auto lub stały kod.
- CLI i web UI na tym samym rdzeniu.

Analogia: **CV + oferta → CV** staje się **autor + dzisiejsze emocje → opowiadanie**.

---

## 2. Decyzje produktowe (MUST, nie negocjować)

1. **Użytkownik nie pisze fikcji.** Input to dane strukturalne + minimalny tekst z limitami egzekwowanymi serwerowo. Brak dużego pola „opisz swój dzień”. Powód: wolne pole zjeżdża w fanfiction/roleplay.
2. **AI wymyśla początek, świat i bohaterów** zgodnie z konwencją autora. Użytkownik dostarcza tylko stan emocjonalny.
3. **Bez narzuconego pozytywizmu.** Trudne emocje mogą być przeżyte w narracji do końca, bez happy endu na siłę i bez morału.
4. **To nie jest terapia.** Warstwa bezpieczeństwa (sekcja 6) działa niezależnie od modelu i ustawień stylu.
5. **Styl z prawdziwych tekstów (RAG)** — opis słowny to szkielet i fallback, korpus to źródło głosu. Czy RAG cokolwiek wnosi, sprawdza harness ewaluacyjny (sekcja 8).
6. **Ciągłość świata** — postaci i sceneria trwają między wpisami (world state z kompakcją).
7. **BYO model, dane lokalnie.** Brak kont, brak chmury, brak telemetrii.

---

## 3. Flow ekranów

### 3.1 Ekran 1 — wybór autora
- Kafelki ładowane z `authors/` (lista MUST być data-driven; dodanie autora = dodanie katalogu, bez zmian w kodzie).
- Start: Dostojewski, Tołstoj, Dickens, Czechow, Kafka (wszyscy public domain).
- Kafelek: nazwa, 1–2 zdania „czego się spodziewać”, status indeksu korpusu.
- Wybór zapamiętany jako domyślny.

### 3.2 Ekran 2 — jak się dziś czujesz
Formularz MUST być w całości ustrukturyzowany:
- **Nastrój (walencja)**: suwak −5…+5.
- **Energia (pobudzenie)**: suwak 0…10.
- **Chipy emocji**: wybór 1–3 z listy (smutek, lęk, złość, spokój, radość, pustka, wdzięczność, znużenie…). Bez osobnej intensywności — walencja + energia już ją kodują.
- **Pytania tak/nie**: 3–4 z puli, każde ma stały `question_id` zapisywany z odpowiedzią (inaczej wykresy w czasie się rozjadą). Przykłady: „Wydarzyło się coś nietypowego?”, „Więcej ludzi czy samotności?”, „Jest coś, czego boisz się jutro?”, „Czy coś się dziś domknęło?”.
- **Słowa kluczowe**: 1–3, limit 60 znaków łącznie.
- **Opcjonalne jedno zdanie**: limit 200 znaków, wyraźnie opcjonalne.
- **Długość**: krótkie / średnie / długie.
- Wiele wpisów dziennie MAY; każdy wpis ma własny timestamp w strefie czasowej z ustawień (domyślnie strefa systemowa).

### 3.3 Ekran 3 — opowiadanie
- Streamowana **wyłącznie proza** (tytuł rozdziału powstaje w drugim wywołaniu, sekcja 5.3, i jest ustalany raz — przy pierwszym wpisie rozdziału).
- Etapy widoczne w UI: „dobieram fragmenty stylu” → „przypominam bohaterów” → „piszę” → „sprawdzam” (filtr wyjścia) → „zapisuję”.
- Wpis zapisuje się automatycznie po przejściu filtra wyjścia (bez ręcznego „zapisz” — patrz ASSUMPTIONS.md "M2").
- Po zakończeniu, dwie jasno rozróżnione opcje (rewizja z sesji "M2.5" — interfejs "książki", zastępuje wcześniejsze „wygeneruj ponownie” / „zmień autora dla tego wpisu”):
  - **„Zakończ ten rozdział”** — zamyka bieżący wątek fabularny jako kompletny (status rozdziału `closed`, wylicza krótkie podsumowanie ze streszczeń jego wpisów), wraca do ekranu 2 na nowy, niezależny wpis.
  - **„Kontynuuj”** — pisze dalszy ciąg TEJ SAMEJ sceny w tym samym, wciąż otwartym rozdziale: ten sam moment, ci sami bohaterowie, ten sam wątek. Osobny szablon promptu (`prompts/continue.md`, sekcja 5.1bis) dostaje dosłowny koniec dotychczasowego tekstu rozdziału (nie streszczenie), obcięty do rozsądnej długości jeśli rozdział jest długi.
- Zwijany panel debug: użyte postaci, wynik filtra wyjścia, wersje promptu i profilu. Liczba chunków RAG dołączy w M3.
- Stream MUST być buforowany po stronie serwera; zerwane połączenie → UI wznawia z bufora, nie generuje od nowa.

### 3.3bis Ekran „Twoja książka” (uproszczony, pełne portfolio to sekcja 3.4/7)
- Lista rozdziałów danego autora w kolejności chronologicznej, każdy jako nagłówek (tytuł) + sklejony tekst wszystkich jego wpisów, czytany jako ciągła proza.
- Rozdziały otwarte i zamknięte są pokazywane, z etykietą statusu; zamknięte mają też krótkie podsumowanie.
- Bez filtrów, wykresów i eksportu — to wchodzi dopiero z pełnym portfolio (3.4/7).

### 3.4 Ekran 4 — portfolio / antologia
- Oś czasu: data, autor, tytuł, tag nastroju, typ wpisu (`story` / `summary_chapter`).
- Filtry: autor, nastrój, okres.
- Wykres nastroju i energii w czasie (SVG po stronie serwera lub lekka biblioteka z CDN).
- Indeks powracających postaci z world state.
- Przycisk „rozdział podsumowujący” (sekcja 7.3).
- Eksport (sekcja 7.5).

### 3.5 Settings drawer
- Provider: OpenAI-compatible / Anthropic / Ollama — przez jeden własny interfejs adaptera (`generate_stream`, `generate_structured`, `embed`). `litellm` MAY być użyte pod spodem, interfejs MUST być własny.
- Trzy sloty modeli: opowiadania, zadania pomocnicze (tańszy), embeddingi. **Embeddingi lokalne (`sentence-transformers`) SHOULD być domyślne.**
- Klucz API: w lokalnym pliku konfiguracyjnym, MUST NIE trafiać do bazy, logów ani eksportu.
- Temperatura, długość, **język UI** i **język opowiadania** jako dwa osobne ustawienia (każdy: auto / kod), locale numerów pomocy.
- Nadpisania per-run przez context manager.

---

## 4. Silnik stylu

### 4.1 Katalog autora
```
authors/<slug>/
  profile.yaml     # metadane + style card (szkielet i fallback)
  corpus/          # teksty public domain wgrywane przez użytkownika (gitignored)
  examples/        # opcjonalne pastisze użytkownika jako wzorce (gitignored)
  index/           # wygenerowany indeks (gitignored)
```
Repo MUST NIE zawierać żadnych tekstów przekładów (mogą być objęte prawami autorskimi). README opisuje, skąd i jak wgrać oryginały.

### 4.2 `profile.yaml`
Pola: `name`, `slug`, `languages`, `era`, `default_setting_hints`, `voice` (składnia, rytm, długość zdań, monolog wewnętrzny, ironia narratora, natura jako lustro stanu), `devices`, `themes`, `character_archetypes`, `lexicon_hints` (per język), `avoid`, `retrieval` (k, chunk size, preferencje tagów per nastrój), `version` (int, kopiowany do wpisu jako `style_profile_version`).

### 4.3 Indeksowanie (`diary index --author <slug> [--reindex] [--tag-tones]`)
- Chunkowanie po akapitach, ~300–600 tokenów, lekki overlap.
- Embeddingi przez wybrany slot; zapis do **SQLite jako blob + brute-force cosine w numpy**. Zewnętrzny vector store MUST NIE być używany (przy kilku tysiącach chunków to zbędny narzut).
- Metadata: książka, rozdział, język, długość.
- Tagowanie tonu tanim modelem jest **MAY**, tylko z flagą `--tag-tones`, cache'owane i wznawialne. Bez tagów retrieval działa po samym embeddingu zapytania nastrojowego.
- Indeks inkrementalny; osobna tabela hashy 8-gramów całego korpusu i lista imion/toponimów (do 4.5).

> **Uproszczona wersja pociągnięta do przodu w sesji "M2.5"** (przed pełnym M3):
> chunkowanie po akapitach działa (`diary/core/style/chunking.py`), ale bez
> `diary index`/persystencji — pliki z `authors/<slug>/corpus/` są wczytywane
> i dzielone w pamięci procesu przy każdym starcie serwera. Brak embeddingów,
> brak tabeli hashy 8-gramów. Patrz 4.4 i ASSUMPTIONS.md "M2.5" — M3 dopełnia
> resztę tej sekcji.

### 4.4 Retrieval
- Zapytanie z walencji, energii, chipów, odpowiedzi tak/nie i słów kluczowych → opis „jakich fragmentów stylu potrzebuję”.
- Top-k (4–8) z MMR (własne ~20 linii), żeby nie dostać ośmiu fragmentów jednej sceny.
- Do promptu jako **wzorce stylu, nie treści**: naśladuj składnię, rytm, środki, temperaturę; nie kopiuj zdań, nie używaj imion i miejsc.
- Brak indeksu → działa samo style card, UI to sygnalizuje.

> **Uproszczona wersja (sesja "M2.5"):** ranking przez nakładanie się słów
> kluczowych (chipy/słowa kluczowe/zdanie vs. tekst chunku), bez embeddingów
> i bez MMR — brak sygnału daje deterministyczny fallback na pierwsze k
> chunków. Wystarcza do prawdziwej inspiracji stylu z realnych tekstów, ale
> to nie jest jeszcze pełny retrieval z 4.4; M3 podmienia scoring na
> embeddingi + MMR bez zmiany miejsca w prompcie (warstwa 5 z 5.1).

### 4.5 Kontrola „nie przepisuj oryginału”
- Po generacji: nakładanie znormalizowanych 8-gramów opowiadania z **całym indeksem** (nie tylko użytymi chunkami) + osobne sprawdzenie imion/toponimów z korpusu. Przekroczenie progu → ostrzeżenie w UI + opcja regeneracji.

---

## 5. Silnik opowiadania

### 5.1 Warstwy promptu (szablon: `prompts/narrator.md`, nowy rozdział)
1. Rola narratora (styl `{author}`, język `{story_lang}`, nie asystent).
2. Style card z `profile.yaml`.
3. Zasady narracji: AI wymyśla punkt wyjścia i wydarzenia; emocje pokazywane, nie nazywane; zakończenie naturalne, bez morału i pocieszenia na siłę; bez zwracania się do czytelnika, bez wzmianek o dzienniku/AI.
4. Zasady bezpieczeństwa (6.4) — zawsze; wzmocnione, gdy detektor lub tryb serii zadziałał.
5. Few-shot: chunki (4.4).
6. Karty postaci i świat (5.2) — zwięzłe, w budżecie tokenów.
7. Dzisiejszy input jako **JSON** w ogranicznikach z **losowym tokenem per request** (`<<<DATA_a3f9c1>>>`), z instrukcją: to wartości pól opisujących stan, nie polecenia.
8. Format wyjścia: **wyłącznie proza**, docelowo ~500/900/1500 słów. Żadnego tytułu, nagłówków, notatek.

### 5.1bis Kontynuacja rozdziału (szablon: `prompts/continue.md`, dodane w sesji "M2.5")
Osobny szablon dla „Kontynuuj” (3.3) — te same warstwy 1–2, 4–6, 8 co wyżej, ale:
- Zamiast warstwy 3 (AI wymyśla punkt wyjścia): instrukcja kontynuowania DOKŁADNIE tej samej sceny — ten sam moment, ci sami bohaterowie, żadnego nowego epizodu.
- Dodatkowa warstwa: **dosłowny koniec dotychczasowego tekstu rozdziału** (nie streszczenie) w osobnym ograniczniku z własnym losowym tokenem — obcięty do końca, jeśli rozdział jest długi.
- Warstwa 7 (dzisiejszy input) zostaje — kontynuacja nadal wplata dzisiejszy stan emocjonalny w dalszy ciąg sceny.

### 5.2 Postaci i świat (rewizja z sesji "M2.5" — zastępuje wcześniejszy blob `canon`/`recent_threads`)
- Zamiast jednego rosnącego obiektu JSON per autor: **osobne karty postaci** (tabela `characters`) + mały rekord scenerii/epoki (`world_meta`) + **rozdziały** (`chapters`) grupujące wpisy jednej ciągłej sceny.
- Karta postaci: imię, `is_alter_ego`, rola, kilka cech (`traits`), relacje do innych postaci po imieniu, status (np. „żywy”/„martwy”/„nieobecny”), `locked`.
- Pierwszy wpis z autorem: AI generuje alter ego (`is_alter_ego: true`), 2–4 powracające postaci z rolami (w tym jedną „obecną bez słów”), scenerię (`world_meta.setting`), epokę.
- Rozdział (`chapters`, status `open`/`closed`) grupuje wpisy jednej ciągłej sceny: otwarty rozdział trzyma pełny tekst dla ewentualnej kontynuacji (5.1bis); po zamknięciu (3.3 „Zakończ ten rozdział”) dostaje krótkie podsumowanie (kilka zdań, złożone z `summary` jego wpisów — bez dodatkowego wywołania modelu) i nie zmienia się już.
- Limity MUST: maks. 8 aktywnych postaci, maks. 6 cech na postać. Przekroczenie liczby postaci → nowe nadmiarowe karty są pomijane (proste capowanie); **kompakcja** (scalanie/archiwizacja nieużywanych postaci) to M4, patrz sekcja 11.
- Reguła konfliktu: nowszy fakt (aktualizacja karty) wygrywa, chyba że karta jest `locked` przez użytkownika.
- **Delta jako wektor injection**: `character_delta` z drugiego wywołania (5.3) to tekst generowany przez model i wracający do promptu. Walidacja MUST obejmować: schemat (pydantic), limity długości każdego pola (np. 200 znaków), odrzucenie wartości zawierających frazy instrukcyjne (wzorce typu „ignoruj”, „od teraz”, „system:”, „zasady:”), brak znaków ograniczników.
- Użytkownik MAY edytować karty w UI (zmiana imienia, usunięcie postaci, `locked`) lub zresetować świat — jeszcze nie zaimplementowane (UI do edycji kart to M4/portfolio zakres).

### 5.3 Dwa wywołania na wpis
1. **Opowiadanie** — streamowane, tylko proza. Nowy rozdział → `prompts/narrator.md`; kontynuacja → `prompts/continue.md` (5.1bis).
2. **Metadane** — tańszym modelem, structured output: `title` (pusty przy kontynuacji — tytuł rozdziału ustala się raz), `mood_tag`, `characters_used`, `character_delta` (5.2), `summary` (1–2 zdania, używane też do podsumowania rozdziału przy zamknięciu — 3.3), `tone_flags` (dla filtra wyjścia, 6.3).

### 5.4 Język
- **Język UI** i **język opowiadania** to osobne ustawienia. Opowiadanie i tytuł w języku opowiadania. Chunki mogą być w innym języku → instrukcja „przenieś styl, nie język”.

### 5.5 Odporność
- Pola tekstowe użytkownika i world state trafiają do promptu wyłącznie jako dane w ogranicznikach. Limity długości egzekwowane serwerowo. Wpis jest zapisywany razem z `prompt_version` i `style_profile_version`.

### 5.6 Błędy
- Zły klucz / brak modelu / limit → czytelny komunikat w UI wskazujący na drawer, bez utraty wypełnionego formularza.
- Timeout streamu → bufor serwera, przycisk „wznów”.

---

## 6. Warstwa bezpieczeństwa

### 6.1 Zasada
Nie terapia. Trzy elementy działają **niezależnie od modelu opowiadania i ustawień stylu**: detektor wejścia (6.2), filtr wyjścia (6.3), baner z numerami pomocy. Instrukcje systemowe (6.4) są czwartą, miękką warstwą — wzmacniają, ale nie są jedynym zabezpieczeniem.

### 6.2 Detektor wejścia
- Działa na słowach kluczowych, opcjonalnym zdaniu oraz kombinacji skrajnie niskiej walencji z odpowiedziami tak/nie.
- Poziom (a): reguły i słowniki lokalne, MUST działać offline. Poziom (b): MAY tani klasyfikator LLM jako drugi głos.
- Testy MUST pokrywać oba kierunki: metaforyczne „umieram z nudów” nie może wyzwalać; realne sygnały muszą.
- Detekcja nigdy nie blokuje zapisu ani generowania — zmienia UI i prompt.

### 6.3 Filtr wyjścia
- Po wygenerowaniu, **przed zapisem i przed pokazaniem pełnego tekstu**: tani klasyfikator ocenia tekst pod kątem: opisów metod krzywdy, estetyzacji/gloryfikacji krzywdy, przedstawienia odejścia jako rozwiązania lub ulgi. Może korzystać z `tone_flags` z drugiego wywołania, ale MUST być osobną decyzją.
- Wynik negatywny → regeneracja z wzmocnionym promptem (maks. 2 próby) → potem fallback: krótkie, spokojne opowiadanie z ograniczonego szablonu, bez wątków ryzyka, plus baner.
- Streaming w UI pokazuje tekst w trakcie generacji; jeśli filtr odrzuci, tekst jest zastępowany z komunikatem „ta wersja nie przeszła sprawdzenia, piszę ponownie”.
- Zdarzenia filtra są logowane lokalnie (bez treści) do debugowania progów.

### 6.4 Reakcja w prompcie (gdy 6.2 zadziałał)
- Postać może przeżywać ciemność w pełni, bez pocieszenia i morału.
- MUST NIE: gloryfikować, estetyzować, opisywać metod, przedstawiać odejścia jako rozwiązania.
- W świecie jest **jedna postać, która po prostu jest obecna** — nie moralizuje, nie radzi, nie zostawia bohatera samego.
- Bez fałszywego optymizmu, ale bez zamykania drzwi.

### 6.5 Baner i stopka
- Statyczny, spokojny baner z numerami z `config/helplines/<locale>.yaml` (dla PL wpisać po weryfikacji: 116 123, 800 70 2222, 112). Nie modal, nie znika po odświeżeniu, jeśli wpis go wywołał.
- Stały dyskretny link „Gdzie szukać pomocy” w stopce, zawsze.

### 6.6 Tryb serii (rozstrzygnięcie decyzji o ruminacji)
- Decyzja: **tak, różnicujemy ton**, bez optymizmu na siłę. Uzasadnienie: aplikacja oddająca codziennie ten sam dół w coraz gęstszej prozie może go utrwalać; dobry autor sam by zmienił perspektywę.
- Wyzwalacz: ≥5 kolejnych wpisów z walencją ≤ −3 (progi w konfiguracji).
- Efekt w prompcie: przesunięcie perspektywy przy zachowaniu tonu autora — inny bohater z kanonu na pierwszym planie, inna pora dnia/roku, ruch zamiast bezruchu, scena z drugą osobą zamiast monologu. MUST NIE: happy end, morał, „będzie lepiej”.
- Efekt w UI: nic nachalnego; baner z 6.5 pojawia się przy serii ≥7 dni niezależnie od detektora.
- Użytkownik MAY wyłączyć tryb serii w ustawieniach; baner przy serii pozostaje.

### 6.7 Dane
- SQLite lokalnie, miękkie usuwanie wpisów (`deleted_at`), `diary backup` kopiuje bazę z datą. Brak telemetrii. Treści idą wyłącznie do wybranego providera.

---

## 7. Portfolio

### 7.1 Schemat (numerowane pliki SQL + tabela `schema_version`; bez alembica)
Zrewidowane w sesji "M2.5" (migracja `0002_character_cards.sql`): `world_states`
zastąpione przez `characters` + `chapters` + `world_meta` (5.2). Brak realnych
danych produkcyjnych w tym momencie, więc cięcie zamiast dopisywania obok.
- `entries`: id, created_at (UTC) + tz, type (`story`/`summary_chapter`), author_slug, parent_entry_id (poprzedni wpis w tym samym rozdziale, przy kontynuacji), chapter_id, mood_inputs JSON, title, story_text, story_lang, mood_tag, summary, characters_used JSON, safety_input_flag, safety_output_result, streak_mode, model_used, prompt_version, style_profile_version, retrieval_chunks JSON, deleted_at.
- `characters`: id, author_slug, name (unique per autor), is_alter_ego, role, traits JSON, relationships JSON, status, locked, archived_at (zarezerwowane pod kompaktację M4), created_at, updated_at.
- `chapters`: id, author_slug, status (`open`/`closed`), title, summary (wypełniane przy zamknięciu), created_at, closed_at.
- `world_meta`: author_slug (PK), setting, era, updated_at.
- `author_index_meta`: author_slug, files, chunk_count, embed_model, tagged (bool), last_indexed_at.
- `safety_events`: id, entry_id, stage, verdict, created_at (bez treści).
- `settings`: klucz–wartość, bez sekretów.

### 7.2 Widoki
Jak w 3.4, plus podgląd wpisu z regeneracją w innym stylu (nowy wpis, `parent_entry_id`).

### 7.3 Rozdział podsumowujący
- Na żądanie lub co miesiąc. Wejście: `summary` wpisów z okresu (nie pełne teksty) + kanon. Zadanie: spleść wątki i łuk emocjonalny okresu w formie rozdziału w stylu autora, bez formy raportu. Zapisany jako `type = summary_chapter`, przechodzi filtr 6.3.

### 7.4 Wglądy (MAY, domyślnie wyłączone)
- Tani model na **danych liczbowych** (walencja, energia, odpowiedzi po `question_id`) formułuje 2–3 neutralne obserwacje. MUST NIE: diagnozy, etykiety kliniczne, interpretacje przyczyn.

### 7.5 Eksport
- `diary export --format md|epub`: strona tytułowa, spis, wpisy chronologicznie, rozdziały podsumowujące jako podziały części. Bez kluczy, bez danych debug.

---

## 8. Ewaluacja (`diary eval`)
- Zestaw 10–15 stałych inputów (różne walencje, energie, autorzy) w `eval/inputs.yaml`.
- Warianty: (A) samo style card, (B) style card + RAG, (C) RAG bez style card.
- Model-sędzia ocenia po rubryce 1–5: wierność składni i rytmu autora; emocje pokazane, nie nazwane; brak morału; brak pocieszenia na siłę; brak „zapachu asystenta”; spójność ze światem.
- Wynik: tabela per wariant + zapis do `eval/results/<data>.json` z `prompt_version`.
- Warunek zamknięcia milestone 3: (B) ≥ (A) w medianie na co najmniej 4 z 6 kryteriów. Jeśli nie — RAG zostaje wyłączony domyślnie, a wniosek ląduje w `ASSUMPTIONS.md`.

---

## 9. Stos i struktura
- Python 3.12, `uv`, FastAPI, `sse-starlette`, `pydantic`, `pydantic-settings`, `httpx`, `typer`, `numpy`, `sentence-transformers` (opcjonalna zależność), SQLite.
- Frontend: Alpine.js + Tailwind z CDN, `index.html` + partiale, zero build.
- CLI: `diary serve`, `diary index`, `diary write`, `diary export`, `diary eval`, `diary backup`, `diary authors list`.
```
diary/
  app/         # FastAPI, SSE, routes, static/
  core/
    settings.py
    llm/       # interfejs + providers
    style/     # profile, chunking, indexing, retrieval, ngram_check
    story/     # prompt_builder, world_state, generation, metadata
    safety/    # input_detector, output_filter, helplines, streak
    portfolio/ # storage, migrations/, queries, summary_chapter, export
    eval/
  cli.py
authors/       # profile.yaml per autor
prompts/       # narrator.md, metadata.md, output_filter.md, summary.md, compaction.md
config/helplines/
eval/
tests/
ASSUMPTIONS.md
README.md
```

---

## 9.1 `.gitignore` (MUST istnieć od pierwszego commita)
```
.env
*.env
authors/*/corpus/
authors/*/examples/
authors/*/index/
*.db
*.sqlite
*.sqlite3
eval/results/
```
Klucze API, korpusy tekstów i baza użytkownika MUST NIE trafiać do repozytorium, nawet lokalnego przed pierwszym pushem.

## 10. Non-goals (MUST NIE robić)
- Brak kont, logowania, multi-user.
- Brak Dockera, brak chmury, brak telemetrii.
- Brak build stepu frontendu (npm, bundler).
- Brak zewnętrznego vector store, brak alembica.
- Brak testów E2E wywołujących prawdziwe LLM w CI (mockowane adaptery).
- Brak wolnego pola tekstowego „opisz swój dzień”.
- Brak funkcji, których nie ma w tym pliku, bez wpisu w `ASSUMPTIONS.md`.

---

## 11. Milestone'y z Definition of Done

### M1 — szkielet end-to-end
Zakres: settings + drawer, adapter LLM (jeden provider), jeden autor na samym style card, ekrany 1–3 ze streamingiem, `prompts/narrator.md` wczytywany z pliku, brak bazy i RAG.
DoD:
1. `uv sync && uv run diary serve` uruchamia UI; wybór autora → formularz → streamowana proza.
2. Zmiana modelu/klucza w drawerze działa bez restartu (context manager).
3. Output to wyłącznie proza — testy na obecność tytułu/nagłówka w streamie przechodzą na mockowanym adapterze.
4. Input trafia do promptu jako JSON w losowym ograniczniku; test jednostkowy buildera to sprawdza.
5. Błędny klucz daje czytelny komunikat, formularz nie znika.

### M2 — pamięć i bezpieczeństwo
Zakres: pełny formularz 3.2, SQLite z migracjami, zapis wpisów, world state (canon/recent, limity, walidacja delty — **struktura zrewidowana w M2.5 poniżej, patrz 5.2**), drugie wywołanie metadanych, detektor wejścia, filtr wyjścia, baner, stopka, bufor streamu.
DoD (spełnione na strukturze world state z czasu M2; M2.5 przeniosła te same gwarancje na karty postaci, patrz M2.5 DoD):
1. Wpis zapisany z `prompt_version`, `style_profile_version`, `question_id` przy odpowiedziach.
2. Drugi wpis z tym samym autorem używa postaci z pierwszego (test na mocku: kanon obecny w prompcie).
3. Delta zawierająca frazę instrukcyjną lub pole >200 znaków jest odrzucana (test).
4. Detektor: zestaw testów z fałszywymi pozytywami i prawdziwymi pozytywami przechodzi.
5. Filtr wyjścia: odrzucony tekst → regeneracja → po 2 próbach fallback (test na mocku zwracającym zły tekst).
6. Baner pojawia się przy detekcji i nie znika po odświeżeniu.

### M2.5 — pamięć postaci, interfejs „książki”, uproszczony RAG (poza kolejnością milestone'ów)
Praca zrobiona po M2 na wyraźną prośbę, wykraczająca poza M2 i sięgająca w SPEC sekcje 4 (RAG), 5.2 (world state) i 7 (portfolio) — patrz ASSUMPTIONS.md "M2.5" po pełne uzasadnienie decyzji.
Zakres: rewizja world state z bloba `canon`/`recent_threads` na karty postaci + `world_meta` + `chapters` (5.2); dwuprzyciskowy interfejs „Zakończ ten rozdział” / „Kontynuuj” z osobnym szablonem `prompts/continue.md` (3.3, 5.1bis); ekran „Twoja książka” do czytania sklejonych rozdziałów (3.3bis) — uproszczona wycinka M4's antologii, bez filtrów/wykresów/eksportu; uproszczony RAG bez embeddingów i MMR (4.3/4.4) — chunkowanie w pamięci, retrieval przez nakładanie słów kluczowych.
DoD:
1. Kontynuacja („Kontynuuj”) wysyła do modelu dosłowny tekst poprzedniego fragmentu rozdziału, nie streszczenie (test na realnym HTTP + SQLite: drugi request zawiera pierwszy `story_text` verbatim).
2. „Zakończ ten rozdział” zamyka rozdział, wylicza podsumowanie ze `summary` jego wpisów bez dodatkowego wywołania LLM, i rozdział jest widoczny jako zamknięty w `/api/authors/{slug}/book`.
3. Karty postaci przetrwają między wpisami tego samego autora (drugi wpis/kontynuacja widzi postaci i scenerię z pierwszego) — test na realnym HTTP + SQLite, nie tylko na mocku.
4. `character_delta` z frazą instrukcyjną lub polem >200 znaków jest odrzucana bez wywalania całych metadanych (test) — ta sama rygorystyczność co M2 DoD #3, przeniesiona na nową strukturę.
5. Author z plikami w `authors/<slug>/corpus/` dostaje w prompcie realne fragmenty tekstu zamiast placeholdera „brak indeksu korpusu” (test na tymczasowym katalogu korpusu, nie na repo dostoevsky, które celowo nie zawiera tekstów źródłowych).
6. Kompakcja world state i tryb serii (6.6) NIE są częścią tej iteracji — zostają w M4 zgodnie z wcześniejszą decyzją (patrz commit historii tej sesji sprzed M2.5).

### M3 — RAG i ewaluacja
Zakres: pełne indeksowanie z embeddingami i persystencją (`diary index`), retrieval z MMR (podmienia uproszczony scoring z M2.5 bez zmiany miejsca w prompcie), kontrola 8-gramów i imion, graceful degradation, `diary eval`.
DoD:
1. `diary index` na przykładowym korpusie tworzy indeks inkrementalnie; ponowne uruchomienie nie przelicza istniejących plików.
2. Retrieval zwraca k różnorodnych chunków (test MMR na syntetycznych wektorach).
3. Test 8-gramów wykrywa wstrzyknięty fragment korpusu.
4. Brak indeksu → generacja działa, UI pokazuje status.
5. `diary eval` produkuje wynik; warunek (B) ≥ (A) sprawdzony, decyzja zapisana w `ASSUMPTIONS.md`.

### M4 — portfolio
Zakres: antologia, filtry, wykres, indeks postaci, rozdział podsumowujący, kompakcja world state, tryb serii, eksport, backup.
DoD:
1. Rozdział podsumowujący zapisany jako `summary_chapter` i widoczny w antologii.
2. Kompakcja po 10 wpisach redukuje kanon do limitów (test).
3. Tryb serii uruchamia się po 5 wpisach ≤ −3 i zmienia prompt (test na mocku).
4. `diary export --format md` daje kompletną książkę bez danych debug i kluczy.
5. `diary backup` tworzy kopię z datą.

### M5 — dopracowanie
Zakres: pozostali autorzy z rzetelnymi profilami, Ollama, lokalne embeddingi jako domyślne, tryb językowy UI/opowiadanie, README z instrukcją korpusów, wglądy (7.4) za flagą.
DoD:
1. Pięć profili z `version`, każdy przechodzi `diary eval` na wariancie A.
2. Ollama działa na wszystkich trzech slotach.
3. README opisuje: wgrywanie korpusów, prawa do przekładów, numery pomocy per locale, jak dodać autora.
