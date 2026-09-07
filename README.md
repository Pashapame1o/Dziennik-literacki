# Dziennik literacki

Dziennik emocji zamieniany w opowiadanie w stylu klasycznego autora. Aplikacja
do użytku osobistego — każdy użytkownik podpina własny model i klucz API.

Pełna specyfikacja: [`SPEC.md`](SPEC.md). Ten plik opisuje tylko jak
uruchomić to, co jest zaimplementowane (Milestone 1, 2 i praca poza kolejnością
"M2.5" — pamięć postaci, kontynuacja rozdziałów, uproszczony RAG — patrz
SPEC sekcja 11).

## Uruchomienie

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

## Autorzy i Twoja książka

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

## Testy

```bash
uv sync --group dev
uv run pytest
```

## Stan projektu

Zaimplementowany zakres i świadome uproszczenia są opisane w
[`ASSUMPTIONS.md`](ASSUMPTIONS.md).
