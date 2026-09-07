# Dziennik literacki

🇵🇱 [Polski](#polski) · 🇬🇧 [English](#english)

---

## Polski

Często się zastanawiałem, czy da się zrobić coś więcej z codziennym journalingiem niż tylko zapisywać: „dzisiaj było tak i tak”.
No i chyba znalazłem rozwiązanie.
Zrobiłem Dziennik literacki — wrzucasz do niego swoje wydarzenia, emocje, ludzi, którzy pojawili się w ciągu dnia, a AI zamienia to w opowiadanie napisane w stylu wybranego autora.
Na razie jest Dostojewski, więc można sobie zafundować trochę egzystencjalnego cierpienia.
Najciekawsze jest to, że aplikacja nie generuje każdego tekstu od zera. Pamięta postacie, wcześniejsze wydarzenia i aktualny rozdział, więc z kolejnych wpisów może powstawać jedna ciągła historia.
Czyli w skrócie:
żyjesz sobie normalnie, a AI robi z tego książkę...
Aplikacja do użytku osobistego — każdy użytkownik podpina własny model i klucz API.

Pełna specyfikacja: [`SPEC.md`](SPEC.md). Ten plik opisuje tylko jak
uruchomić to, co jest zaimplementowane (Milestone 1, 2 i praca poza kolejnością
"M2.5" — pamięć postaci, kontynuacja rozdziałów, uproszczony RAG — patrz
SPEC sekcja 11).

### Uruchomienie

```bash
uv sync
uv run diary serve
```

Otwórz `http://127.0.0.1:8000`. Wybierz autora → wypełnij formularz → dostaniesz
streamowane opowiadanie, zapisane lokalnie w SQLite (domyślnie `diary.db` w
katalogu, z którego uruchomiono `diary serve`; ścieżkę zmienia się zmienną
`DIARY_DB_PATH`). Baza jest w `.gitignore` — nie trafia do repozytorium.

Ustaw klucz API, model opowiadania i model zadań pomocniczych (metadane,
sprawdzanie treści) w panelu ustawień (ikona ⚙) — działa od razu, bez
restartu serwera. Domyślny adres API to `https://api.openai.com/v1`; presety
w panelu ustawień wypełniają adres i przykładową nazwę modelu dla OpenAI i
Google Gemini (przez jego warstwę zgodną z OpenAI), dowolny inny endpoint
zgodny z OpenAI API też zadziała.

### Autorzy i Twoja książka

Autorzy są wczytywani z katalogu `authors/<slug>/profile.yaml` — dodanie
nowego autora nie wymaga zmian w kodzie. W tej chwili jest jeden: Dostojewski.

Każdy wpis należy do **rozdziału** — po wygenerowaniu opowiadania wybierasz
„Zakończ ten rozdział” (zamyka wątek, wraca do nowego wpisu) albo „Kontynuuj”
(pisze dalszy ciąg tej samej sceny). Link „Twoja książka” w nagłówku pokazuje
wszystkie rozdziały danego autora jako ciągły tekst.

Domyślnie Dostojewski działa wyłącznie na opisie stylu z `profile.yaml`. Żeby
dołożyć bezpośrednią inspirację z prawdziwych tekstów, wgraj własne pliki do
`authors/dostoevsky/corpus/` — instrukcja formatu i legalnych źródeł jest w
[`authors/dostoevsky/README.md`](authors/dostoevsky/README.md). To uproszczona
wersja RAG (bez embeddingów/MMR — patrz `ASSUMPTIONS.md` "M2.5"); pełne
indeksowanie przychodzi w M3, patrz `SPEC.md` sekcja 4 i 8.

`authors/<slug>/corpus/`, `examples/` i `index/` są w `.gitignore` — repo nie
zawiera żadnych tekstów źródłowych (mogą być objęte prawami autorskimi).

### Testy

```bash
uv sync --group dev
uv run pytest
```

### Stan projektu

Zaimplementowany zakres i świadome uproszczenia są opisane w
[`ASSUMPTIONS.md`](ASSUMPTIONS.md).

---

## English

I'd often wondered whether daily journaling could be more than just writing down "today went like this."
I think I found an answer.
I built Dziennik literacki ("Literary Diary") — you feed it your day's events, emotions, and the people who showed up in it, and AI turns that into a short story written in the style of a chosen author.
Right now there's just Dostoevsky, so you can treat yourself to a bit of existential suffering.
The interesting part: the app doesn't generate every text from scratch. It remembers characters, past events, and the current chapter, so a sequence of entries can grow into one continuous story.
So, in short:
you go on living your life, and the AI turns it into a book...
A personal-use app — each user brings their own model and API key.

Full spec: [`SPEC.md`](SPEC.md) (in Polish). This file only covers how to
run what's actually implemented (Milestones 1, 2, and the out-of-band
"M2.5" work — character memory, chapter continuation, simplified RAG — see
SPEC section 11).

### Running it

```bash
uv sync
uv run diary serve
```

Open `http://127.0.0.1:8000`. Pick an author → fill in the form → get a
streamed story, saved locally in SQLite (`diary.db` by default, in whatever
directory you ran `diary serve` from; change the path with the
`DIARY_DB_PATH` env var). The database is gitignored — it never reaches the
repo.

Set your API key, story model, and helper model (metadata, content checks)
in the settings panel (⚙ icon) — takes effect immediately, no server
restart. The default API address is `https://api.openai.com/v1`; presets in
the settings panel fill in the address and an example model name for OpenAI
and Google Gemini (via its OpenAI-compatible layer), and any other
OpenAI-compatible endpoint works too.

### Authors and your book

Authors are loaded from `authors/<slug>/profile.yaml` — adding a new author
needs no code changes. Right now there's one: Dostoevsky.

Every entry belongs to a **chapter** — once a story is generated, you choose
"End this chapter" (closes the thread, returns to a new entry) or "Continue"
(writes the next part of the same scene). The "Your book" link in the header
shows every chapter for an author as one continuous read.

By default, Dostoevsky runs purely on the style description in
`profile.yaml`. To add direct inspiration from real texts, drop your own
files into `authors/dostoevsky/corpus/` — the format and legal-source
instructions are in
[`authors/dostoevsky/README.md`](authors/dostoevsky/README.md). This is a
simplified version of RAG (no embeddings/MMR — see `ASSUMPTIONS.md`
"M2.5"); full indexing lands in M3, see `SPEC.md` sections 4 and 8.

`authors/<slug>/corpus/`, `examples/`, and `index/` are gitignored — the
repo ships with no source texts (they may be copyrighted).

### Tests

```bash
uv sync --group dev
uv run pytest
```

### Project status

The implemented scope and the deliberate simplifications are documented in
[`ASSUMPTIONS.md`](ASSUMPTIONS.md) (in Polish).
