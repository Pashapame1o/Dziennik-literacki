# Dziennik literacki

Dziennik emocji zamieniany w opowiadanie w stylu klasycznego autora. Aplikacja
do użytku osobistego — każdy użytkownik podpina własny model i klucz API.

Pełna specyfikacja: [`SPEC.md`](SPEC.md). Ten plik opisuje tylko jak
uruchomić to, co jest zaimplementowane (Milestone 1 — patrz SPEC sekcja 11).

## Uruchomienie

```bash
uv sync
uv run diary serve
```

Otwórz `http://127.0.0.1:8000`. Wybierz autora → wypełnij formularz → dostaniesz
streamowane opowiadanie.

Ustaw klucz API i model w panelu ustawień (ikona ⚙ w prawym górnym rogu) —
działa od razu, bez restartu serwera. Domyślny adres API to
`https://api.openai.com/v1`; dowolny endpoint zgodny z OpenAI API zadziała.

## Autorzy

Autorzy są wczytywani z katalogu `authors/<slug>/profile.yaml` — dodanie
nowego autora nie wymaga zmian w kodzie. W tej chwili jest jeden:
Dostojewski, działający wyłącznie na opisie stylu (bez korpusu, bez RAG —
to przychodzi w M3, patrz `SPEC.md` sekcja 4 i 8).

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
