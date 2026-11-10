"""Tests for the officer action buttons (permission gate + wiring)."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from spam_remover.views import OfficerActionView


def make_interaction(*, ban=False, kick=False):
    interaction = MagicMock()
    perms = MagicMock()
    perms.ban_members = ban
    perms.kick_members = kick
    interaction.user.guild_permissions = perms
    interaction.response.send_message = AsyncMock()
    return interaction


def test_view_exposes_three_buttons():
    view = OfficerActionView(target_user_id=1, target_label="x")
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert len(buttons) == 3
    assert {b.label for b in buttons} == {"Kick", "Ban", "Not spam"}


async def test_officer_with_ban_permission_is_allowed():
    view = OfficerActionView(target_user_id=1, target_label="x")
    interaction = make_interaction(ban=True)

    assert await view.interaction_check(interaction) is True
    interaction.response.send_message.assert_not_called()


async def test_officer_with_kick_permission_is_allowed():
    view = OfficerActionView(target_user_id=1, target_label="x")
    interaction = make_interaction(kick=True)

    assert await view.interaction_check(interaction) is True


async def test_kick_button_kicks_target():
    view = OfficerActionView(target_user_id=42, target_label="x")
    interaction = make_interaction(kick=True)
    interaction.guild = MagicMock()
    interaction.guild.kick = AsyncMock()
    interaction.user.mention = "<@1>"
    interaction.message = MagicMock()
    interaction.message.embeds = []
    interaction.response.edit_message = AsyncMock()

    kick_button = next(c for c in view.children if getattr(c, "label", None) == "Kick")
    await kick_button.callback(interaction)

    interaction.guild.kick.assert_awaited_once()
    kicked = interaction.guild.kick.call_args.args[0]
    assert kicked.id == 42
    interaction.response.edit_message.assert_awaited_once()


async def test_non_officer_is_blocked_with_ephemeral_notice():
    view = OfficerActionView(target_user_id=1, target_label="x")
    interaction = make_interaction(ban=False, kick=False)

    assert await view.interaction_check(interaction) is False
    interaction.response.send_message.assert_awaited_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.parametrize("action", ["Kick", "Ban"])
async def test_manual_officer_actions_work(action):
    view = OfficerActionView(target_user_id=42, target_label="x")
    interaction = make_interaction(kick=True, ban=True)
    interaction.guild.kick = AsyncMock()
    interaction.guild.ban = AsyncMock()
    interaction.message.embeds = []
    interaction.response.edit_message = AsyncMock()
    button = next(c for c in view.children if c.label == action)

    assert button.disabled is False
    assert await view.interaction_check(interaction) is True
    await button.callback(interaction)

    action_method = interaction.guild.kick if action == "Kick" else interaction.guild.ban
    action_method.assert_awaited_once()
    assert action_method.call_args.args[0].id == 42
    interaction.response.edit_message.assert_awaited_once()
