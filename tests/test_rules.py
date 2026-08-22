"""Table-driven tests for the pure rule-based classifier."""

import pytest

from spam_remover.detection.rules import Decision, evaluate

# Real-world spam joiner messages that should be caught instantly (no LLM needed).
SPAM_SAMPLES = [
    "🎁 FREE NITRO for the first 10 people, dm me to claim!",
    "Free discord nitro here: http://discrod-gift.ru/claim",
    "Steam gift card giveaway, claim your $50 now",
    "guys i'm giving away free robux, dm me",
    "🚀 Crypto airdrop! claim your free tokens at bit.ly/abc123",
    "join my server for free stuff @everyone discord.gg/scam123",
    "WINNER!! you have been selected, claim your prize: http://sketchy.xyz",
]

# Legitimate first messages from new members that must NOT be flagged.
CLEAN_SAMPLES = [
    "hi everyone, excited to join the club!",
    "hey all, when is the next meeting?",
    "thanks for adding me 😄",
    "Does anyone have notes from last week's workshop?",
    "gm",
]

# Borderline messages: a link, mention, or scam-product keyword without a
# strong phrase. These should be handed to the LLM rather than auto-SPAM.
SUSPECT_SAMPLES = [
    "check out this project i built https://github.com/me/cool-thing",
    "here's the reading for class: https://example.edu/syllabus.pdf",
    "@everyone don't forget the meeting at 5",
    # Soft everyday promo wording + link must NOT auto-SPAM.
    "here's a free tutorial https://example.com/guide",
    "got a discount code for the pizza place https://example.com/coupon",
    # Scam-product keyword + link is SUSPECT (Claude), not rules-SPAM.
    "check this nitro link https://example.com/claim",
    "crypto tips for beginners https://example.com/blog",
]


@pytest.mark.parametrize("content", SPAM_SAMPLES)
def test_obvious_spam_is_flagged(content):
    result = evaluate(content)
    assert result.decision is Decision.SPAM, f"expected SPAM for {content!r}"
    assert result.reason


@pytest.mark.parametrize("content", CLEAN_SAMPLES)
def test_legitimate_messages_are_clean(content):
    result = evaluate(content)
    assert result.decision is Decision.CLEAN, f"expected CLEAN for {content!r}"


@pytest.mark.parametrize("content", SUSPECT_SAMPLES)
def test_borderline_messages_are_suspect(content):
    result = evaluate(content)
    assert result.decision is Decision.SUSPECT, f"expected SUSPECT for {content!r}"


def test_mention_everyone_flag_counts_as_mass_mention():
    # A reply/system mention may set the flag without literal "@everyone" text.
    # Soft wording alone no longer auto-SPAMs; mass mention → SUSPECT for Claude.
    result = evaluate("come get your free gift", mention_everyone=True)
    assert result.decision is Decision.SUSPECT


def test_invite_plus_everyone_is_still_spam():
    result = evaluate("join my server for free stuff @everyone discord.gg/scam123")
    assert result.decision is Decision.SPAM


def test_extra_keywords_extend_detection():
    # Club-specific spam wording can be added via config. Without the extra
    # keyword the message has no signals and is clean; the keyword promotes it
    # to SUSPECT (Claude), never auto-SPAM on keyword alone.
    plain = "anyone want a sneaker drop alert"
    assert evaluate(plain).decision is Decision.CLEAN
    promoted = evaluate(plain, extra_keywords=["sneaker drop"])
    assert promoted.decision is Decision.SUSPECT


def test_empty_message_is_clean():
    assert evaluate("").decision is Decision.CLEAN
    assert evaluate("   ").decision is Decision.CLEAN


def test_result_reason_is_human_readable():
    result = evaluate("free nitro giveaway dm me")
    assert isinstance(result.reason, str) and len(result.reason) > 0
