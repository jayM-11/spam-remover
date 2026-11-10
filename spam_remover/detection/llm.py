"""Claude-backed spam classification for messages not caught by local spam rules."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a Discord moderation assistant for a student club. You judge whether "
    "a server message is spam, regardless of how long the author has been a member. "
    "Spammers advertise free "
    "giveaways, free Discord Nitro, gift cards, crypto/NFT airdrops, account boosts, "
    "adult content, or push people to DM them or click a sketchy link to 'claim' "
    "something. Legitimate members say hello, ask questions, or share relevant "
    "links (GitHub, course materials, news).\n\n"
    "Respond with ONLY a compact JSON object and nothing else, in the form:\n"
    '{"is_spam": true|false, "reason": "<one short sentence>"}\n'
    "Be conservative: only mark is_spam true when you are confident it is a scam or "
    "unsolicited advertisement. When unsure, return false."
)


@dataclass(frozen=True)
class LLMVerdict:
    is_spam: bool
    reason: str


class SpamJudge(Protocol):
    """Interface the orchestrator depends on; easy to fake in tests."""

    async def classify(self, content: str) -> LLMVerdict: ...


class ClaudeJudge:
    """SpamJudge backed by the Anthropic API (Claude Haiku by default)."""

    def __init__(self, client, model: str) -> None:
        # `client` is an anthropic.AsyncAnthropic; injected so tests stay offline.
        self._client = client
        self._model = model

    async def classify(self, content: str) -> LLMVerdict:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=128,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content or "(empty message)"}],
            )
            text = "".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            ).strip()
            return _parse_verdict(text)
        except Exception:  # noqa: BLE001 - never let moderation crash on an API hiccup
            logger.exception("Claude classification failed; failing safe to not-spam")
            return LLMVerdict(False, "LLM unavailable; defaulted to not-spam")


def _parse_verdict(text: str) -> LLMVerdict:
    """Extract the JSON verdict from the model's reply, failing safe to not-spam."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        logger.warning("Could not find JSON in LLM reply: %r", text)
        return LLMVerdict(False, "Unparseable LLM reply; defaulted to not-spam")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in LLM reply: %r", text)
        return LLMVerdict(False, "Invalid LLM JSON; defaulted to not-spam")

    is_spam = bool(data.get("is_spam", False))
    reason = str(data.get("reason") or "").strip() or "No reason given"
    return LLMVerdict(is_spam, reason)
