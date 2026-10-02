"""Evidence selection and conservative composition guards for Resume Studio."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

_TOKEN = re.compile(r"[a-z][a-z0-9+#.-]{1,}", re.IGNORECASE)
# Currency, sign, and magnitude are material parts of a quantified claim. A
# rewrite from $10 to 10, -20% to 20%, or 10 million to 10 billion must not pass
# merely because the digits appear in the source evidence.
_NUMBER = re.compile(
    r"(?<![\w])(?:[+\-−]\s*)?(?:[$€£¥]\s*)?(?:[+\-−]\s*)?"
    r"\d[\d,]*(?:\.\d+)?(?:e[+\-]?\d+)?"
    r"(?:\s*(?:%|x\b|(?:thousand|million|billion|trillion)\b|[kmb]\b))?",
    re.IGNORECASE,
)
_STOP = {"and", "the", "for", "with", "from", "that", "this", "have", "into", "you", "your", "our", "are", "was", "were", "will", "job", "role", "team", "work", "using", "use", "all", "not"}
ONE_PAGE_TARGET_CHARACTERS = 3200  # planning heuristic only; export remains ordinary text.


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN.findall(value) if token.lower() not in _STOP}


def select_verified_facts(job_text: str, facts: Iterable[object], *, limit: int = 30) -> list[tuple[object, int]]:
    """Rank immutable verified source facts by stable JD token overlap and recency."""
    target = _tokens(job_text)
    ranked: list[tuple[object, int]] = []
    for fact in facts:
        if not getattr(fact, "user_verified", False) or getattr(fact, "archived_at", None) is not None:
            continue
        text = " ".join((getattr(fact, "title", None) or "", getattr(fact, "fact_text", ""), *getattr(fact, "tags", [])))
        terms = _tokens(text)
        overlap = len(target & terms)
        score = round(100 * overlap / max(1, len(target)))
        ranked.append((fact, score))
    ranked.sort(key=lambda pair: (-pair[1], -int(getattr(pair[0], "occurred_at", None).toordinal() if getattr(pair[0], "occurred_at", None) else 0), str(getattr(pair[0], "id", ""))))
    return ranked[: max(0, min(limit, 50))]


def numeric_claims(value: str) -> set[str]:
    return {
        re.sub(r"[\s,]", "", match.group(0)).replace("−", "-").casefold()
        for match in _NUMBER.finditer(value)
    }


def unsupported_numeric_claims(text: str, evidence: Iterable[str]) -> list[str]:
    supported: set[str] = set()
    for fact in evidence:
        supported.update(numeric_claims(fact))
    return sorted(numeric_claims(text) - supported)


@dataclass(frozen=True)
class CompositionReview:
    characters: int
    one_page_target_characters: int
    page_status: str
    extractable_text: bool
    universal_ats_claim: bool = False


def composition_review(text: str) -> CompositionReview:
    return CompositionReview(
        characters=len(text),
        one_page_target_characters=ONE_PAGE_TARGET_CHARACTERS,
        page_status="WITHIN_ONE_PAGE_TARGET" if len(text) <= ONE_PAGE_TARGET_CHARACTERS else "OVERFLOW_REQUIRES_REVIEW",
        extractable_text=bool(text.strip()) and "\x00" not in text,
    )
