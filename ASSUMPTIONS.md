# ASSUMPTIONS

Decisions taken where SPEC.md left room, or where an M1 shortcut departs
from the eventual (M2+) shape. Each entry says what was assumed and why.

## M1 — szkielet end-to-end

- **First commit predates `.gitignore`.** The planned step order (`.gitignore`
  first, then `git init`) assumed a fresh repo, but `SPEC.md` was already
  committed before this work began. `.gitignore` was added as the first file
  of this session's work instead. No secrets, corpus, or DB files were
  present in that earlier commit, so nothing sensitive leaked.

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
  hardcoded Polish by design. `ui_language` exists as a `Settings` field for
  shape-stability but has no effect yet.

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

## M1.5 — Gemini via the OpenAI-compatible adapter

- **`generate_story` always sends a `user`-role turn alongside the `system`
  prompt**, not just `system` alone. Real OpenAI tolerates a system-only
  message list; Google's Gemini OpenAI-compat layer maps `system` →
  `systemInstruction` and everything else → `contents`, and 400s with
  "contents is not specified" if `contents` ends up empty. The added
  `USER_TURN_TRIGGER` message is content-free (the actual task lives entirely
  in the system prompt) — it exists purely to give the request a non-system
  turn, and costs nothing on providers that never needed it.

## M2 — pamięć i bezpieczeństwo

- **Kompakcja world state i tryb serii (SPEC 6.6) zostały odłożone do M4**,
  mimo że pojawiły się w opisie zakresu tej iteracji — sekcja 11 SPEC.md
  przypisuje obie funkcje jawnie do M4 (a `diary/core/safety/streak.py` miał
  już od M1 komentarz "out of scope until M4"). Potwierdzone z użytkownikiem
  przed implementacją. M2 implementuje tylko limity world state (8
  postaci / 25 faktów / 5 wątków) przez proste capowanie i FIFO na
  `recent_threads` — bez inteligentnego scalania faktów czy archiwizacji
  nieużywanych postaci, które wymagają osobnego wywołania LLM (M4 DoD #2).
  Tryb serii (przesunięcie perspektywy, baner po serii ≥7 dni) nie jest
  wywoływany nigdzie w M2; kolumna `entries.streak_mode` istnieje w schemacie
  (SPEC 7.1) i zawsze zapisuje `False`.

- **Brak ręcznego przycisku „Zapisz".** Wpis zapisuje się automatycznie do
  SQLite od razu po przejściu (lub ostatecznym nieprzejściu — fallback też
  się zapisuje) filtra wyjścia, wewnątrz zadania w tle, niezależnie od tego,
  czy przeglądarka jest jeszcze podłączona. DoD M2 #1 nie wymaga akcji
  użytkownika, a M4 (antologia) potrzebuje kompletnej historii wpisów, nie
  tylko tych ręcznie zatwierdzonych. Ekran 3 z SPEC 3.3 wciąż ma "wygeneruj
  ponownie" i "zmień autora dla tego wpisu" — oba tworzą nowy wpis z
  `parent_entry_id` wskazującym na poprzedni.

- **Filtr wyjścia (6.3) jest wywołaniem LLM (na `model_helper`), nie regułami
  offline.** SPEC nazywa go "tanim klasyfikatorem" i explicite dopuszcza
  korzystanie z `tone_flags` z drugiego wywołania — to sugeruje model, nie
  słownik. Detektor wejścia (6.2) natomiast MUST działać offline, więc tam
  zostały reguły/regex. Konsekwencja: testy filtra wyjścia mockują
  `generate_structured`, nie sprawdzają realnych fraz w tekście.

- **"maks. 2 próby" (6.3) = 2 regeneracje ponad pierwszą próbę**, czyli do 3
  wywołań generowania łącznie zanim wejdzie fallback. Rozstrzygnięcie
  niejednoznaczności w literalnym brzmieniu SPEC; test
  `test_output_filter_rejects_twice_then_falls_back` koduje to wprost.

- **Wzmocnione `safety_rules` (6.4) są używane w dwóch niezależnych
  sytuacjach**: gdy detektor wejścia (6.2) zadziała od pierwszej próby, ORAZ
  przy każdej regeneracji wywołanej przez filtr wyjścia (6.3) — niezależnie
  od tego, czy detektor cokolwiek wykrył. SPEC 6.3 mówi wprost o
  "wzmocnionym prompcie" przy regeneracji, więc drugi przypadek nie jest
  rozszerzeniem, tylko literalnym czytaniem.

- **Baner pomocy (6.5) pokazuje się szerzej niż tylko "przy detekcji"**:
  również gdy filtr wyjścia ostatecznie użył fallbacku (`safety_output_result
  == "fallback"`), nawet jeśli detektor wejścia nic nie wykrył. To
  celowe poszerzenie na rzecz bezpieczeństwa (fallback oznacza, że model
  faktycznie wygenerował ryzykowną treść, co jest silniejszym sygnałem niż
  sama obecność słowa kluczowego), nie wymóg literalny DoD #6 — który mówi
  tylko o detekcji i jest spełniony niezależnie od tego rozszerzenia.

- **Numery pomocy w `config/helplines/pl.yaml` są przepisane wprost z treści
  SPEC.md** ("dla PL wpisać po weryfikacji: 116 123, 800 70 2222, 112"), nie
  zweryfikowane ponownie na żywym źródle w tej sesji. Etykiety operatorów
  ("Telefon Zaufania dla Dzieci i Młodzieży", "Centrum Wsparcia dla Osób w
  Kryzysie Psychicznym") to mój opis, nie cytat z oficjalnego źródła — **do
  sprawdzenia przed realnym użyciem**, SPEC 6.5 też tego wymaga ("po
  weryfikacji").

- **Bufor streamu (3.3) jest w pamięci procesu, nie w SQLite**, kluczowany
  losowym `generation_id`, z leniwym czyszczeniem (ukończone generacje
  wygasają po 15 minutach, sprzątane przy okazji następnego
  `POST /api/generate`). Nie przeżywa restartu serwera — uznane za
  wystarczające dla osobistej, jednoprocesowej aplikacji bez wielu klientów
  jednocześnie. Wznowienie po zerwanym połączeniu to ręczny przycisk
  "Wznów" (SPEC 5.6 literalnie: "przycisk wznów"), nie cichy auto-retry.

- **SQLite przez zwykłe blokujące `sqlite3` (stdlib), nowe połączenie na każde
  zadanie generowania**, bez puli połączeń ani `aiosqlite`. SPEC 9 nie
  wymaga sterownika async; przy skali "jeden użytkownik, jeden proces" narzut
  otwierania połączenia jest nieistotny, a prostota ważniejsza.

- **`model_helper` trafił do `SettingsOverride` i do panelu ustawień w M2.**
  Istniał w `Settings` już od M1, ale niczego nie robił (żadne wywołanie go
  nie używało) i dlatego nie był eksponowany per-run. Od M2 realnie zasila
  wywołanie metadanych i filtr wyjścia, więc brak możliwości nadpisania go w
  drawerze byłby luką, nie oszczędnością.

- **Panel debug na ekranie 3 to natywny `<details>`**, bez dodatkowego stanu
  JS do zwijania/rozwijania. Pokazuje id wpisu, `mood_tag`, użyte postaci,
  wynik filtra wyjścia, `prompt_version` i `style_profile_version`. Liczba
  chunków z RAG (SPEC 3.3) nie jest pokazywana — RAG to M3, panel dostanie to
  pole wtedy.

- **Tytuł opowiadania pokazuje się dopiero po zakończeniu generowania**
  (razem z resztą `entryInfo` z eventu `result`), nie podczas streamowania —
  zgodnie z SPEC 3.3 ("tytuł powstaje w drugim wywołaniu") i 3.3
  ("Streamowana wyłącznie proza").

- **`tone_flags` z wywołania metadanych przechodzą przez tę samą kontrolę
  wstrzyknięć co pola world state** (`check_safe_text` + allow-lista znanych
  etykiet), zanim trafią do promptu filtra wyjścia — to też jest tekst
  generowany przez model, wracający do kolejnego wywołania LLM, więc
  traktowany jak potencjalny wektor iniekcji, tak samo jak `world_state_delta`.

## M2.5 — pamięć postaci, interfejs „książki", uproszczony RAG

Praca zrobiona na wyraźną prośbę po zaakceptowaniu M2, wykraczająca poza M2
i dotykająca SPEC sekcji 4 (RAG), 5.2 (world state) i 7 (portfolio). SPEC.md
zaktualizowany równolegle (sekcje 3.3, 3.3bis, 4.3, 4.4, 5.1bis, 5.2, 5.3,
7.1, nowa podsekcja 11 „M2.5").

### Dlaczego blob `canon`/`recent_threads` z M2 nie udźwignąłby kontynuacji

To była wyraźna prośba, żeby to wyjaśnić, więc konkretnie:

1. **Nigdzie nie było dosłownego tekstu.** `recent_threads` trzymał co
   najwyżej 5 krótkich stringów (streszczeń), `canon.facts` — płaską listę
   zdań. „Kontynuuj" wymaga literalnego końca poprzedniego fragmentu, żeby
   model dokończył zdanie/scenę tam, gdzie się urwała — blob nigdy tego nie
   przechowywał, bo nie było takiej potrzeby przed tą funkcją. Nie da się
   tego dociągnąć bez zmiany struktury: trzeba było gdzieś trzymać, które
   wpisy należą do tej samej, wciąż otwartej sceny, i mieć dostęp do ich
   pełnej treści.
2. **Fakty nie były przypisane do niczego konkretnego.** `canon.facts: list[str]`
   nie miał pojęcia, że fakt X dotyczy postaci Y. Zmiana statusu postaci
   (np. śmierć) mogła tylko dopisać kolejny string do listy, nigdy
   zaktualizować/nadpisać istniejący — SPEC 5.2 M2 rozwiązywał to
   kompaktacją (odłożoną do M4), a nie strukturą. Karta postaci z polem
   `status` rozwiązuje to od razu, bez czekania na kompaktację.
3. **Cały blob renderował się w każdym prompcie niezależnie od potrzeby.**
   Limity (8 postaci / 25 faktów / 5 wątków) ograniczały rozmiar, ale to
   wciąż był jeden nieprzewidywalny akapit prozy do sparsowania przez model
   za każdym razem. Karty postaci mają stały, mały kształt (kilka pól na
   kartę) — łatwiejsze do budżetowania tokenów i do testowania w izolacji.

Test regresyjny na to konkretnie:
`test_continue_prompt_contains_literal_prior_text_verbatim` w
`tests/test_chapter_continuity_endpoint.py` — asercja, że drugi (kontynuujący)
request zawiera pierwszy `story_text` znak w znak, przez prawdziwy HTTP +
SQLite, nie tylko na skonstruowanym ręcznie obiekcie.

### Zmiana modelu danych

- `world_states` **usunięte**, nie zostawione obok (migracja `0002`, brak
  realnych danych produkcyjnych w tym momencie — tania migracja, tak jak
  prosiłeś). Zastąpione przez `characters` (jedna karta = jeden wiersz),
  `world_meta` (sceneria/epoka, jeden wiersz per autor) i `chapters`
  (grupowanie wpisów jednej ciągłej sceny, status open/closed, podsumowanie
  po zamknięciu).
- `entries.world_state_version` **usunięte** (SQLite ≥3.35 obsługuje
  `DROP COLUMN`, sprawdzone: 3.50.4 w tym środowisku). `entries.chapter_id`
  dodane. `entries.parent_entry_id` zostaje, ale teraz ma jednoznaczne
  znaczenie: „poprzedni wpis w tym samym rozdziale" (ustawiane serwerowo
  przy kontynuacji, nie przez klienta).
- Limit **8 aktywnych postaci** (SPEC 5.2 M2) przeniesiony 1:1 na nową
  strukturę — proste capowanie nowych kart ponad limit, bez kompaktacji
  (patrz niżej). Dodany limit **6 cech na postać** (`traits`), którego M2
  nie potrzebowało (blob nie miał odpowiednika pola).

### Przyciski ekranu 3: usunięte „wygeneruj ponownie" / „zmień autora"

To jest realna zmiana możliwości aplikacji, nie tylko przemianowanie — warto
to wiedzieć, jeśli ich brak zaskoczy. Oba konfliktowały semantycznie z
modelem rozdziałów: „wygeneruj ponownie" sugerowało odrzucenie i zastąpienie
ostatniego wpisu, a auto-save (M2) już wtedy zapisywał go do bazy — z
rozdziałami to musiałoby albo cofać zapis, albo tworzyć osierocony wpis.
„Zmień autora dla tego wpisu" nie ma sensu w obrębie jednego, spójnego stylu
rozdziału. Zastąpione przez „Zakończ ten rozdział" / „Kontynuuj" — jeśli
użytkownik jednak chce mieć możliwość odrzucenia/przerobienia ostatniej
próby przed zdecydowaniem, czy kontynuować czy zakończyć, to osobna prośba
do rozważenia później, nie coś, co po cichu zniknęło jako przeoczenie.

### Uproszczony RAG (SPEC 4.3/4.4)

- **Chunkowanie**: akapity pakowane do budżetu słów (przybliżenie „tokenów"
  z `profile.yaml`, bez prawdziwego tokenizera) z lekkim overlapem
  (`diary/core/style/chunking.py`). Zgodne z 4.3 co do zasady, nie co do
  precyzji liczenia tokenów.
- **Retrieval bez embeddingów i bez MMR**: scoring przez nakładanie się
  słów (chipy + słowa kluczowe + zdanie vs. tekst chunku,
  `diary/core/style/retrieval.py`). Brak sygnału → deterministyczny fallback
  na pierwsze k chunków w kolejności pliku. To świadome uproszczenie
  wskazane w prośbie — M3 podmienia to na prawdziwe embeddingi (przez slot
  `model_embedding` już istniejący w `Settings` od M1) + MMR, bez zmiany
  miejsca w prompcie (warstwa 5 z 5.1 zostaje).
- **Brak `diary index` i brak persystencji indeksu.** Pliki z
  `authors/<slug>/corpus/` są wczytywane i dzielone w pamięci procesu
  (`functools.lru_cache`) przy pierwszym użyciu po starcie. Dodanie/zmiana
  plików korpusu wymaga restartu `diary serve`, żeby zostały zauważone —
  zaakceptowane jako rozsądne dla osobistej aplikacji jednoprocesowej,
  restartowanej rzadko. Tabela `author_index_meta` (SPEC 7.1) istnieje w
  schemacie, ale nic jej jeszcze nie zapisuje — to M3.
- **Kontrola 8-gramów/imion (SPEC 4.5) nie jest zaimplementowana.** Explicite
  wykluczona z tej iteracji w prośbie użytkownika.
- **`AuthorSummary.has_corpus`** dodane obok istniejącego `has_index` (M3),
  żeby kafelek autora na ekranie 1 dawał widoczny sygnał po wgraniu plików
  korpusu — bez tego README instrukcyjne w `authors/dostoevsky/` obiecywałoby
  informację zwrotną w UI, której nic by faktycznie nie dawało.
- **`authors/dostoevsky/README.md`** (nie w `authors/dostoevsky/corpus/` —
  ten katalog jest w całości w `.gitignore`, więc plik tam umieszczony
  nigdy nie trafiłby do repo, nawet jako sama instrukcja) opisuje format,
  konwencję nazw i ogólne źródła tekstów domeny publicznej (Wolne Lektury,
  Project Gutenberg, Wikiźródła) bez wskazywania konkretnych linków do
  książek — legalność treści jest wprost scedowana na użytkownika, zgodnie
  z prośbą.

### Podsumowanie rozdziału bez dodatkowego wywołania LLM

„Zakończ ten rozdział" liczy podsumowanie jako złączenie pól `summary`
poszczególnych wpisów tego rozdziału (`diary/core/story/chapters.py:
summarize_chapter`) — każdy wpis ma już takie pole z własnego wywołania
metadanych (SPEC 5.3). Zero dodatkowego kosztu/wywołania modelu przy
zamykaniu rozdziału. Jeśli jakość takiego podsumowania okaże się
niewystarczająca (np. rozdział z wieloma kontynuacjami daje sklejone, mało
spójne zdania), naturalnym rozszerzeniem byłoby dedykowane wywołanie
podsumowujące przy zamknięciu — odłożone, bo obecne rozwiązanie działa i
jest tańsze.

### Kompakcja i tryb serii nadal odłożone do M4

Potwierdzenie decyzji z M2 (SPEC 11, `diary/core/safety/streak.py`) — mimo
że ta iteracja dotyka dokładnie tej części world state, którą kompaktacja
miałaby porządkować, nie została zaimplementowana teraz. Limit 8 postaci
egzekwowany jest nadal przez proste capowanie nowych kart, nie przez
scalanie/archiwizację.
