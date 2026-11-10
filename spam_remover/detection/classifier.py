"""Catch obvious spam with rules, then ask Claude about remaining messages."""

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
    """Use local spam rules first and consult the LLM for every other message."""

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
        # An absence of keyword signals does not prove a message is clean.
        llm_verdict = await self._judge.classify(content)
        return Verdict(llm_verdict.is_spam, llm_verdict.reason, source="llm")
