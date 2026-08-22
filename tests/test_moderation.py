"""Tests for moderation actions with fully mocked Discord objects."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import pytest

from spam_remover.config import Config
from spam_remover.detection.classifier import Verdict
from spam_remover.moderation import Moderator
from spam_remover.views import OfficerActionView


def make_config(**overrides) -> Config:
    base = Config(
        discord_token="x",
        anthropic_api_key="y",
        officer_channel_id=999,
        dry_run=False,
    )
    return replace(base, **overrides)


def make_message():
    message = MagicMock()
    message.content = "free nitro, dm me to claim"
    message.delete = AsyncMock()
    message.channel = MagicMock()
    message.channel.id = 123
    message.channel.mention = "<#123>"
    message.channel.name = "general"
    member = MagicMock()
    member.id = 4242
    member.__str__ = lambda self: "Spammer#0001"
    member.kick = AsyncMock()
    message.author = member
    return message, member


def make_client(officer_channel):
    client = MagicMock()
    client.get_channel = MagicMock(return_value=officer_channel)
    return client


VERDICT = Verdict(is_spam=True, reason="Matched known scam phrase", source="rules")


async def test_normal_mode_deletes_kicks_and_notifies():
    message, member = make_message()
    channel = MagicMock()
    channel.send = AsyncMock()
    moderator = Moderator(make_config(dry_run=False), make_client(channel))

    await moderator.handle_spam(message, VERDICT)

    message.delete.assert_awaited_once()
    member.kick.assert_awaited_once()
    assert "Matched known scam phrase" in member.kick.call_args.kwargs["reason"]
    channel.send.assert_awaited_once()
    # The officer notice carries the interactive Kick / Ban / Not-spam controls.
    assert isinstance(channel.send.call_args.kwargs["view"], OfficerActionView)
    embed = channel.send.call_args.kwargs["embed"]
    fields = {field.name: field.value for field in embed.fields}
    assert fields["Channel"] == "<#123>"


async def test_dry_run_notifies_but_does_not_delete_or_kick():
    message, member = make_message()
    channel = MagicMock()
    channel.send = AsyncMock()
    moderator = Moderator(make_config(dry_run=True), make_client(channel))

    await moderator.handle_spam(message, VERDICT)

    message.delete.assert_not_called()
    member.kick.assert_not_called()
    channel.send.assert_awaited_once()


async def test_missing_officer_channel_does_not_crash():
    message, _ = make_message()
    moderator = Moderator(make_config(dry_run=True), make_client(None))

    # Should log an error and return without raising.
    await moderator.handle_spam(message, VERDICT)
