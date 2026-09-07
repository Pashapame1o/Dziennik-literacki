# Korpus dla Dostojewskiego — jak wgrać własne teksty źródłowe

Ten plik jest instrukcją dla Ciebie (użytkownika), nie treścią promptu. Aplikacja
używa korpusu wyłącznie jako bezpośredniej inspiracji stylu (SPEC 4.3/4.4) —
fragmenty trafiają do promptu jako "wzorce składni i rytmu", nigdy jako treść
do skopiowania.

**Legalność treści jest Twoją odpowiedzialnością.** Nic w tym repo nie
pobiera ani nie generuje tekstów źródłowych — to świadoma decyzja: prawa do
konkretnych przekładów (zwłaszcza na polski) bywają wciąż chronione, nawet
gdy oryginał jest domeną publiczną. Wgrywaj tylko teksty, co do których masz
pewność, że możesz ich użyć w ten sposób (domena publiczna w Twojej
jurysdykcji, przekład z wygasłymi prawami, tekst własny/oryginalny).

## Gdzie umieścić pliki

```
authors/dostoevsky/corpus/
  zbrodnia-i-kara.txt
  biesy.md
  ...
```

- Format: `.txt` lub `.md`, kodowanie UTF-8.
- Jeden plik = jedna książka (albo dowolny fragment, jeśli wolisz dzielić inaczej).
- Akapity oddzielone **pustą linią** — od tego zależy jakość dzielenia na fragmenty
  (SPEC 4.3 chunking działa na granicach akapitów).
- Cały katalog `authors/*/corpus/` jest w `.gitignore` — pliki nigdy nie trafią
  do repozytorium ani nikomu nie zostaną przypadkiem wypchnięte.

## Skąd wziąć legalne teksty

Nie podaję bezpośrednich linków do konkretnych książek (mogłyby się zmienić
albo prowadzić donikąd) — poniżej ogólnie znane źródła tekstów domeny
publicznej, które warto samodzielnie przeszukać:

- **Wolne Lektury** (wolnelektury.pl) — polskie przekłady klasyki w domenie
  publicznej lub na wolnej licencji, z jasno opisanym statusem prawnym
  każdego tekstu.
- **Project Gutenberg** (gutenberg.org) — głównie oryginały i starsze
  przekłady angielskie, przydatne jeśli chcesz `story_language: angielski`
  albo fragmentów w oryginalnym rosyjskim.
- **Wikiźródła / Wikisource** — czasem mają przekłady nieobecne gdzie indziej,
  zawsze sprawdź status prawny konkretnego tekstu na stronie.

Po pobraniu: zapisz jako zwykły `.txt`/`.md` (nie PDF — aplikacja nie parsuje
PDF-ów), usuń ewentualne strony redakcyjne/przypisy wydawcy, zostaw sam tekst
literacki.

## Co się stanie po wgraniu

Restart `diary serve` wystarczy — pliki są wczytywane i dzielone na fragmenty
przy starcie procesu (w pamięci, bez trwałego indeksu — to uproszczona wersja
RAG, pełne indeksowanie z embeddingami przychodzi w M3, patrz `ASSUMPTIONS.md`
"M2.5" i `SPEC.md` sekcja 4.3). Kafelek autora na ekranie 1 pokaże wtedy
"źródło stylu: pliki wgrane (bez pełnego indeksu)", a fragmenty stylu zaczną
się pojawiać w prompcie zamiast placeholdera "brak indeksu korpusu".
