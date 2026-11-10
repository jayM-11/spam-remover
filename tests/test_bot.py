"""Message scanning across member ages and configured exclusions."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from spam_remover.bot import SpamRemoverClient
from spam_remover.config import Config
from spam_remover.detection.classifier import Verdict


@pytest.fixture
async def client():
    config = Config(
        discord_token="test", anthropic_api_key="test", officer_channel_id=999,
        trusted_role_ids=frozenset({42}), monitored_channel_ids=frozenset({123}),
    )
    classifier = MagicMock()
    classifier.classify = AsyncMock(return_value=Verdict(True, "Spam", "llm"))
    moderator = MagicMock()
    moderator.handle_spam = AsyncMock()
    client = SpamRemoverClient(config, classifier, moderator)
    yield client
    await client.close()


def make_message():
    message = MagicMock()
    message.created_at = datetime.now(timezone.utc)
    message.author = MagicMock(spec=discord.Member)
    message.author.bot = False
    message.author.roles = []
    message.channel.id = 123
    message.content = "Please contact me for prizes"
    message.mention_everyone = False
    return message


@pytest.mark.parametrize("days_since_join", [0, 3, 365, None])
async def test_scans_messages_regardless_of_join_age(client, days_since_join):
    message = make_message()
    message.author.joined_at = (
        None if days_since_join is None
        else datetime.now(timezone.utc) - timedelta(days=days_since_join)
    )

    await client.on_message(message)

    client._classifier.classify.assert_awaited_once_with(
        message.content, mention_everyone=False
    )
    client._moderator.handle_spam.assert_awaited_once_with(
        message, client._classifier.classify.return_value
    )


@pytest.mark.parametrize("exclusion", ["bot", "dm", "trusted_role", "channel", "non_member"])
async def test_skips_excluded_messages(client, exclusion):
    message = make_message()
    if exclusion == "bot":
        message.author.bot = True
    elif exclusion == "dm":
        message.guild = None
    elif exclusion == "trusted_role":
        role = MagicMock()
        role.id = 42
        message.author.roles = [role]
    elif exclusion == "channel":
        message.channel.id = 456
    else:
        message.author = MagicMock(spec=discord.User)
        message.author.bot = False

    await client.on_message(message)

    client._classifier.classify.assert_not_awaited()
    client._moderator.handle_spam.assert_not_awaited()


async def test_clean_verdict_does_not_moderate(client):
    client._classifier.classify.return_value = Verdict(False, "Normal chat", "llm")

    await client.on_message(make_message())

    client._classifier.classify.assert_awaited_once()
    client._moderator.handle_spam.assert_not_awaited()


async def test_ignores_messages_created_before_process_start(client):
    message = make_message()
    message.created_at = client._started_at - timedelta(seconds=1)

    await client.on_message(message)

    client._classifier.classify.assert_not_awaited()
    client._moderator.handle_spam.assert_not_awaited()
