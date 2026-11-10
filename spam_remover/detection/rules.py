"""Pure, dependency-free rule classifier for spam-joiner messages.

This is the fast first stage of detection. It runs on every scanned message and
returns one of three decisions:

* ``SPAM``   – near-certain spam (strong phrases, or invite+@everyone); act
  immediately, no LLM call.
* ``CLEAN``  – no local spam signals; still hand off to the LLM.
* ``SUSPECT``– some signal (link, mass mention, or scam-product keyword) but not
  enough to act alone; hand off to the LLM.

Keeping this module pure (no I/O, no Discord/Anthropic imports) makes it cheap to
unit-test against a table of real spam and legitimate messages.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Sequence
from dataclasses import dataclass


class Decision(enum.Enum):
    SPAM = "spam"
    CLEAN = "clean"
    SUSPECT = "suspect"


@dataclass(frozen=True)
class RuleResult:
    decision: Decision
    reason: str


# High-confidence scam phrasing. A single match is enough to call it spam.
_STRONG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"free\s+(?:discord\s+)?nitro"),
    re.compile(r"nitro\s+(?:giveaway|for\s+free)"),
    re.compile(r"free\s+robux"),
    re.compile(r"steam\s+gift"),
    re.compile(r"\bairdrop\b"),
    re.compile(r"claim\s+(?:your|free)\b"),
    re.compile(r"you(?:'?ve|\s+have)\s+(?:been\s+)?(?:selected|won)"),
    re.compile(r"free\s+(?:gift\s+)?card"),
    re.compile(r"first\s+\d+\s+people"),
)

# Narrow scam-product signals only. Soft everyday words (free, gift, discount,
# giveaway, …) are intentionally omitted — they show up in normal chat and used
# to auto-flag promo+link as SPAM. These keywords alone are SUSPECT; combined
# with a link or mass mention they are still SUSPECT (Claude decides), never
# auto-SPAM.
_PROMO_KEYWORDS: frozenset[str] = frozenset(
    {
        "nitro",
        "robux",
        "airdrop",
        "crypto",
        "nft",
    }
)

_INVITE_RE = re.compile(r"(?:discord\.gg|discord(?:app)?\.com/invite)/\S+")
_LINK_RE = re.compile(r"(?:https?://|www\.)\S+|(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl)/\S+")
_MENTION_RE = re.compile(r"@(?:everyone|here)\b")


def _keyword_matches(keyword: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def evaluate(
    content: str,
    *,
    mention_everyone: bool = False,
    extra_keywords: Sequence[str] = (),
) -> RuleResult:
    """Classify a message body using only fast, local rules.

    ``mention_everyone`` should be set when Discord reports the message pinged
    @everyone/@here even if the literal text was stripped. ``extra_keywords`` are
    club-specific promo terms appended to the built-in list.
    """
    text = content.lower()

    for pattern in _STRONG_PATTERNS:
        if pattern.search(text):
            return RuleResult(
                Decision.SPAM,
                f"Matched known scam phrase: /{pattern.pattern}/",
            )

    has_invite = _INVITE_RE.search(text) is not None
    has_link = has_invite or _LINK_RE.search(text) is not None
    mass_mention = mention_everyone or _MENTION_RE.search(text) is not None

    all_keywords = set(_PROMO_KEYWORDS) | {k.lower() for k in extra_keywords}
    matched = sorted(kw for kw in all_keywords if _keyword_matches(kw, text))
    has_promo = bool(matched)

    promo_desc = f"scam-product wording ({', '.join(matched)})" if matched else ""

    # Invite + @everyone/@here is still near-certain spam-joiner behavior.
    if has_invite and mass_mention:
        return RuleResult(
            Decision.SPAM,
            "Server-invite link combined with a mass mention",
        )

    # Promo keywords + link/mention used to auto-SPAM; that false-positived on
    # normal "free tutorial" / "discount" style messages. Hand these to Claude.
    if has_promo and (has_link or mass_mention or has_invite):
        if has_invite:
            carrier = "a server-invite link"
        elif has_link:
            carrier = "a link"
        else:
            carrier = "a mass mention"
        return RuleResult(
            Decision.SUSPECT,
            f"{promo_desc.capitalize()} combined with {carrier}",
        )

    if has_link:
        return RuleResult(Decision.SUSPECT, "Contains a link but no obvious scam wording")
    if mass_mention:
        return RuleResult(Decision.SUSPECT, "Mass mention (@everyone/@here)")
    if has_promo:
        return RuleResult(Decision.SUSPECT, f"Contains {promo_desc}")

    return RuleResult(Decision.CLEAN, "No spam signals")
