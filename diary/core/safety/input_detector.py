"""Input safety detector (SPEC 6.2): offline rules/dictionaries, no network
call, no model. Runs on the optional sentence, keywords, and the combination
of very low valence with certain yes/no answers.

Detection never blocks saving or generating (SPEC 6.1/6.2) — the caller only
uses the result to pick the reinforced safety_rules layer (6.4) and to show
the helpline banner (6.5). False negatives are more costly than false
positives here, but SPEC 6.2 explicitly requires both directions to be
tested: metaphorical Polish idioms ("umieram z nudów") MUST NOT trigger.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from diary.core.story.mood_input import MoodInput

# Real crisis signals: explicit first-person statements of intent or despair
# about living. Phrased narrowly (specific verb + object combinations) so
# they don't overlap with common Polish idioms that reuse "umierać"/"zabić"
# as hyperbole (see _SAFE_IDIOMS below and the false-positive test set).
_CRISIS_PATTERNS = [
    re.compile(r"chc[ęe]\s+si[ęe]\s+zabi[ćc]", re.IGNORECASE),
    re.compile(r"chc[ęe]\s+odebra[ćc]\s+sobie\s+[żz]ycie", re.IGNORECASE),
    re.compile(r"nie\s+chc[ęe]\s+ju[żz]\s+[żz]y[ćc]", re.IGNORECASE),
    re.compile(r"nie\s+ma\s+sensu\s+(dalej\s+)?[żz]y[ćc]", re.IGNORECASE),
    re.compile(r"chc[ęe]\s+znikn[ąa][ćc]\s+na\s+zawsze", re.IGNORECASE),
    re.compile(r"koniec\s+ze\s+mn[ąa]", re.IGNORECASE),
    re.compile(r"sko[ńn]czy[ćc]\s+ze\s+sob[ąa]", re.IGNORECASE),
    re.compile(r"samob[óo]jstw", re.IGNORECASE),
    re.compile(r"samob[óo]jcz", re.IGNORECASE),
    re.compile(r"mam\s+plan[,\s]+[żz]eby\s+(si[ęe]\s+)?zabi", re.IGNORECASE),
    re.compile(r"nikomu\s+nie\s+b[ęe]d[ęe]\s+ju[żz]\s+ci[ęe][żz]arem", re.IGNORECASE),
    # English, in case keywords/sentence are typed in English:
    re.compile(r"\bkill\s+myself\b", re.IGNORECASE),
    re.compile(r"\bwant\s+to\s+die\b", re.IGNORECASE),
    re.compile(r"\bend\s+it\s+all\b", re.IGNORECASE),
    re.compile(r"\bsuicid", re.IGNORECASE),
]

# Idioms that reuse the same rough vocabulary ("umierać", "zabić", "koniec")
# purely as hyperbole. Not used to suppress a match (the patterns above are
# already narrow enough to not match these) — kept here as the documented,
# tested false-positive set (SPEC 6.2: "metaforyczne 'umieram z nudów' nie
# może wyzwalać").
KNOWN_SAFE_METAPHORS = [
    "umieram z nudów",
    "umieram z głodu",
    "umieram ze śmiechu",
    "zabiłabym za kawę",
    "zabiłbym za kawę",
    "śmiertelnie znudzony",
    "to był koniec świata, ale przeżyję",
    "koniec tygodnia wreszcie",
    "nie mogę się doczekać, aż to się skończy",
]

# Combination rule (SPEC 6.2): extreme low valence alone is not a crisis
# signal (plenty of hard, honest sad days aren't emergencies), but paired
# with certain yes/no answers it's a softer secondary signal worth flagging.
_COMBINATION_VALENCE_THRESHOLD = -4
_COMBINATION_TRIGGER_QUESTION_IDS = {"afraid_tomorrow", "something_closed"}


@dataclass(frozen=True)
class DetectionResult:
    triggered: bool
    reasons: tuple[str, ...] = ()


def _scan_text(text: str) -> str | None:
    for pattern in _CRISIS_PATTERNS:
        if pattern.search(text):
            return f"phrase_match:{pattern.pattern}"
    return None


def detect(mood_input: MoodInput) -> DetectionResult:
    reasons: list[str] = []

    if mood_input.sentence:
        reason = _scan_text(mood_input.sentence)
        if reason:
            reasons.append(reason)

    for keyword in mood_input.keywords:
        reason = _scan_text(keyword)
        if reason:
            reasons.append(reason)

    if mood_input.valence <= _COMBINATION_VALENCE_THRESHOLD:
        flagged_answers = [
            qid
            for qid in _COMBINATION_TRIGGER_QUESTION_IDS
            if mood_input.answers.get(qid) is True
        ]
        if flagged_answers:
            reasons.append(f"low_valence_combination:{','.join(sorted(flagged_answers))}")

    return DetectionResult(triggered=bool(reasons), reasons=tuple(reasons))
