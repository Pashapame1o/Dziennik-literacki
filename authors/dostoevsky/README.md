# Korpus dla Dostojewskiego / Dostoevsky corpus

🇵🇱 [Polski](#polski) · 🇬🇧 [English](#english)

---

## Polski

### Jak wgrać własne teksty źródłowe

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

### Gdzie umieścić pliki

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

### Skąd wziąć legalne teksty

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

### Co się stanie po wgraniu

Restart `diary serve` wystarczy — pliki są wczytywane i dzielone na fragmenty
przy starcie procesu (w pamięci, bez trwałego indeksu — to uproszczona wersja
RAG, pełne indeksowanie z embeddingami przychodzi w M3, patrz `ASSUMPTIONS.md`
"M2.5" i `SPEC.md` sekcja 4.3). Kafelek autora na ekranie 1 pokaże wtedy
"źródło stylu: pliki wgrane (bez pełnego indeksu)", a fragmenty stylu zaczną
się pojawiać w prompcie zamiast placeholdera "no corpus index for this author".

---

## English

### How to upload your own source texts

This file is instructions for you (the user), not prompt content. The app
uses the corpus purely as direct style inspiration (SPEC 4.3/4.4) — excerpts
go into the prompt as "syntax and rhythm patterns," never as content to copy.

**Content legality is your responsibility.** Nothing in this repo downloads
or generates source texts — that's a deliberate choice: rights to specific
translations (especially into Polish) can still be protected even when the
original is public domain. Only upload texts you're sure you can use this
way (public domain in your jurisdiction, a translation with expired rights,
or your own original text).

### Where to put the files

```
authors/dostoevsky/corpus/
  crime-and-punishment.txt
  demons.md
  ...
```

- Format: `.txt` or `.md`, UTF-8 encoding.
- One file = one book (or any fragment, if you'd rather split it differently).
- Paragraphs separated by a **blank line** — the quality of chunking depends
  on this (SPEC 4.3 chunking splits on paragraph boundaries).
- The whole `authors/*/corpus/` directory is gitignored — the files will
  never reach the repository or get accidentally pushed anywhere.

### Where to get legal texts

I'm not linking directly to specific books (links could change or go
nowhere) — below are generally known public-domain text sources worth
searching yourself:

- **Wolne Lektury** (wolnelektury.pl) — Polish translations of the classics,
  public domain or under a free license, with the legal status of each text
  clearly stated.
- **Project Gutenberg** (gutenberg.org) — mostly originals and older English
  translations, useful if you want `story_language: angielski` or fragments
  in the original Russian.
- **Wikisource** — sometimes has translations you won't find elsewhere,
  always check the legal status of the specific text on the page.

After downloading: save as plain `.txt`/`.md` (not PDF — the app doesn't
parse PDFs), strip out any editorial pages/publisher footnotes, and keep
only the literary text itself.

### What happens after uploading

Just restart `diary serve` — files are read and split into chunks at
process startup (in memory, no persistent index — this is the simplified
version of RAG; full embedding-based indexing lands in M3, see
`ASSUMPTIONS.md` "M2.5" and `SPEC.md` section 4.3). The author tile on
screen 1 will then show "źródło stylu: pliki wgrane (bez pełnego indeksu)"
("style source: files uploaded, no full index"), and style excerpts will
start appearing in the prompt instead of the "no corpus index for this
author" placeholder.
