"""Actions taken when a message is judged to be spam: delete, kick, notify."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord

from .config import Config
from .detection.classifier import Verdict
from .views import OfficerActionView

logger = logging.getLogger(__name__)

_MAX_FIELD = 1024


class Moderator:
    """Carries out moderation for a spam verdict.

    In ``DRY_RUN`` mode it skips the destructive delete/kick steps and only posts
    an officer notice, so the club can validate detection before going live.
    """

    def __init__(self, config: Config, client: object | None = None) -> None:
        self._config = config
        self._client = client

    def set_client(self, client: object) -> None:
        """Attach the gateway client (used to resolve the officer channel)."""
        self._client = client

    async def handle_spam(self, message, verdict: Verdict) -> None:
        member = message.author
        if not self._config.dry_run:
            await self._delete_message(message)
            await self._kick_member(member, verdict)
        await self._notify_officers(message, member, verdict)

    async def _delete_message(self, message) -> None:
        try:
            await message.delete()
        except discord.HTTPException:
            logger.exception("Failed to delete spam message %s", getattr(message, "id", "?"))

    async def _kick_member(self, member, verdict: Verdict) -> None:
        reason = f"Spam joiner: {verdict.reason}"[:512]
        try:
            await member.kick(reason=reason)
        except discord.HTTPException:
            logger.exception("Failed to kick member %s", getattr(member, "id", "?"))

    async def _notify_officers(self, message, member, verdict: Verdict) -> None:
        channel = self._client.get_channel(self._config.officer_channel_id)
        if channel is None:
            logger.error(
                "Officer channel %s not found; cannot post notice",
                self._config.officer_channel_id,
            )
            return
        view = OfficerActionView(
            target_user_id=getattr(member, "id", 0),
            target_label=str(member),
        )
        try:
            await channel.send(embed=self._build_embed(message, member, verdict), view=view)
        except discord.HTTPException:
            logger.exception("Failed to post officer notice")

    def _build_embed(self, message, member, verdict: Verdict) -> discord.Embed:
        dry = self._config.dry_run
        embed = discord.Embed(
            title="🚫 Spam joiner detected" if dry else "🚫 Spam joiner removed",
            color=discord.Color.orange() if dry else discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="User", value=f"{member} (`{getattr(member, 'id', '?')}`)", inline=False)
        embed.add_field(name="Channel", value=_channel_mention(message), inline=False)
        embed.add_field(name="Message", value=(message.content or "(no text)")[:_MAX_FIELD], inline=False)
        embed.add_field(name="Reason", value=(verdict.reason or "—")[:_MAX_FIELD], inline=False)
        embed.add_field(name="Detected by", value=verdict.source, inline=True)
        embed.add_field(
            name="Action",
            value="Flagged only (DRY RUN)" if dry else "Message deleted & user kicked",
            inline=True,
        )
        embed.set_footer(
            text="Kicked users can rejoin — re-invite them if this was a mistake. Ban blocks rejoin."
        )
        return embed


def _channel_mention(message) -> str:
    """Clickable Discord channel mention, with a name/id fallback."""
    channel = getattr(message, "channel", None)
    if channel is None:
        return "unknown"
    mention = getattr(channel, "mention", None)
    if isinstance(mention, str) and mention:
        return mention
    channel_id = getattr(channel, "id", None)
    if isinstance(channel_id, int):
        return f"<#{channel_id}>"
    name = getattr(channel, "name", None)
    if isinstance(name, str) and name:
        return f"#{name}"
    return "unknown"
