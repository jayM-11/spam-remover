"""Orchestrates the two detection stages: fast rules, then Claude for borderline."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .llm import SpamJudge
from .rules import Decision, evaluate


@dataclass(frozen=True)
class Verdict:
    is_spam: bool
    reason: str
    source: str  # "rules" or "llm"


class Classifier:
    """Combines the rule pre-filter with an LLM second opinion.

    The LLM is only consulted for ``SUSPECT`` messages, so clean and obviously
    spammy messages cost nothing.
    """

    def __init__(self, judge: SpamJudge, *, extra_keywords: Sequence[str] = ()) -> None:
        self._judge = judge
        self._extra_keywords = tuple(extra_keywords)

    async def classify(self, content: str, *, mention_everyone: bool = False) -> Verdict:
        result = evaluate(
            content,
            mention_everyone=mention_everyone,
            extra_keywords=self._extra_keywords,
        )

        if result.decision is Decision.SPAM:
            return Verdict(True, result.reason, source="rules")
        if result.decision is Decision.CLEAN:
            return Verdict(False, result.reason, source="rules")

        # SUSPECT: ask the LLM.
        llm_verdict = await self._judge.classify(content)
        return Verdict(llm_verdict.is_spam, llm_verdict.reason, source="llm")
