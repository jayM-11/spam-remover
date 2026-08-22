"""Tests for the rules->LLM orchestration, especially the cost short-circuits."""

import pytest

from spam_remover.detection.classifier import Classifier
from spam_remover.detection.llm import LLMVerdict


class SpyJudge:
    """A fake SpamJudge that records calls and returns a canned verdict."""

    def __init__(self, verdict: LLMVerdict):
        self.verdict = verdict
        self.calls: list[str] = []

    async def classify(self, content: str) -> LLMVerdict:
        self.calls.append(content)
        return self.verdict


async def test_obvious_spam_does_not_call_llm():
    judge = SpyJudge(LLMVerdict(False, "should never run"))
    classifier = Classifier(judge)

    verdict = await classifier.classify("free nitro giveaway, dm me to claim")

    assert verdict.is_spam is True
    assert verdict.source == "rules"
    assert judge.calls == []  # short-circuited, no API cost


async def test_clean_message_does_not_call_llm():
    judge = SpyJudge(LLMVerdict(True, "should never run"))
    classifier = Classifier(judge)

    verdict = await classifier.classify("hi everyone, glad to be here!")

    assert verdict.is_spam is False
    assert verdict.source == "rules"
    assert judge.calls == []


async def test_suspect_message_is_routed_to_llm_and_respects_spam_verdict():
    judge = SpyJudge(LLMVerdict(True, "advertising a sketchy giveaway site"))
    classifier = Classifier(judge)

    content = "check this out https://totally-legit-prizes.example"
    verdict = await classifier.classify(content)

    assert judge.calls == [content]
    assert verdict.is_spam is True
    assert verdict.source == "llm"
    assert verdict.reason == "advertising a sketchy giveaway site"


async def test_suspect_message_respects_not_spam_verdict():
    judge = SpyJudge(LLMVerdict(False, "looks like a normal project link"))
    classifier = Classifier(judge)

    verdict = await classifier.classify("my portfolio: https://example.com/me")

    assert verdict.is_spam is False
    assert verdict.source == "llm"


async def test_extra_keywords_are_passed_into_rules():
    judge = SpyJudge(LLMVerdict(False, "n/a"))
    classifier = Classifier(judge, extra_keywords=["sneaker drop"])

    # With the extra keyword this becomes SUSPECT and reaches the LLM.
    await classifier.classify("anyone want a sneaker drop alert")

    assert judge.calls == ["anyone want a sneaker drop alert"]
