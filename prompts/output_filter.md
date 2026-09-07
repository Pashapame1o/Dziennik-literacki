# prompts/output_filter.md — szablon filtra wyjścia (SPEC 6.3)
# prompt_version: 1
# Osobna decyzja od drugiego wywołania (metadane): tani model, tylko klasyfikacja.
# tone_flags z metadanych MAY pomóc, ale to MUSI być osobna ocena tekstu, nie ich powtórzenie.

Oceniasz opowiadanie pod kątem trzech konkretnych zagrożeń — nic więcej.

## OPOWIADANIE
{delimiter_open}
{story_text}
{delimiter_close}

## SUGESTIE Z WCZEŚNIEJSZEJ ANALIZY (mogą być mylne, zweryfikuj sam)
tone_flags: {tone_flags}

## OCEŃ, CZY TEKST ZAWIERA
1. Opis metody wyrządzenia sobie lub komuś krzywdy (konkretny sposób, środek, technikę).
2. Estetyzację lub gloryfikację krzywdy, cierpienia, odejścia (przedstawienie jako piękne, godne podziwu, pociągające).
3. Przedstawienie odejścia/śmierci jako rozwiązania problemu lub formy ulgi.

Trudne emocje, smutek, żal, rozpacz przeżywane w pełni to NIE jest powód do odrzucenia — to zamierzony ton tej aplikacji. Odrzucasz tylko za punkty 1–3 powyżej.

## ZWRÓĆ WYŁĄCZNIE OBIEKT JSON
- `verdict`: `"pass"` albo `"regenerate"`.
- `reasons` (lista stringów, max 5, max 100 znaków każdy): krótkie, konkretne powody, jeśli `regenerate`. Pusta lista, jeśli `pass`.
