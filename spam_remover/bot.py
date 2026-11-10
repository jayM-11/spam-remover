"""Entry point: the always-on Discord gateway client and its event handlers.

Handlers are intentionally thin — all detection and moderation logic lives in
the ``detection`` package and ``moderation`` module, which are unit-tested.
"""

from __future__ import annotations

import logging

import discord
from anthropic import AsyncAnthropic

from .config import Config
from .detection.classifier import Classifier
from .detection.llm import ClaudeJudge
from .moderation import Moderator

logger = logging.getLogger(__name__)


def has_trusted_role(member: discord.Member, trusted_role_ids: frozenset[int]) -> bool:
    if not trusted_role_ids:
        return False
    return any(role.id in trusted_role_ids for role in getattr(member, "roles", []))


class SpamRemoverClient(discord.Client):
    def __init__(self, config: Config, classifier: Classifier, moderator: Moderator) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # privileged: read message text
        intents.members = True  # privileged: member and role information
        super().__init__(intents=intents)
        self._started_at = discord.utils.utcnow()
        self._config = config
        self._classifier = classifier
        self._moderator = moderator

    async def on_ready(self) -> None:
        mode = "DRY RUN (no kicks)" if self._config.dry_run else "LIVE (will delete & kick)"
        logger.info("Logged in as %s — %s", self.user, mode)
        self._log_visible_channels()

    def _log_visible_channels(self) -> None:
        """Print which text channels the bot can currently read (Discord perms)."""
        monitored = self._config.monitored_channel_ids
        for guild in self.guilds:
            me = guild.me
            if me is None:
                logger.warning("Server %s (%s): bot member not cached yet", guild.name, guild.id)
                continue
            visible: list[str] = []
            for channel in guild.text_channels:
                perms = channel.permissions_for(me)
                if not (perms.view_channel and perms.read_message_history):
                    continue
                will_scan = not monitored or channel.id in monitored
                tag = "" if will_scan else " [skipped by MONITORED_CHANNEL_IDS]"
                visible.append(f"#{channel.name} ({channel.id}){tag}")
            if visible:
                logger.info(
                    "Server %s (%s) — can read %d text channel(s):\n  %s",
                    guild.name,
                    guild.id,
                    len(visible),
                    "\n  ".join(visible),
                )
            else:
                logger.warning(
                    "Server %s (%s) — cannot read any text channels (check View Channel perms)",
                    guild.name,
                    guild.id,
                )

    def _should_scan(self, message: discord.Message) -> bool:
        if message.created_at < self._started_at:
            return False
        if message.author.bot or message.guild is None:
            return False
        if not isinstance(message.author, discord.Member):
            return False
        if self._config.monitored_channel_ids and message.channel.id not in self._config.monitored_channel_ids:
            return False
        if has_trusted_role(message.author, self._config.trusted_role_ids):
            return False
        return True

    async def on_message(self, message: discord.Message) -> None:
        if not self._should_scan(message):
            return
        verdict = await self._classifier.classify(
            message.content, mention_everyone=message.mention_everyone
        )
        if verdict.is_spam:
            logger.info(
                "Spam from %s (%s) via %s: %s",
                message.author, message.author.id, verdict.source, verdict.reason,
            )
            await self._moderator.handle_spam(message, verdict)


def build_client(config: Config) -> SpamRemoverClient:
    anthropic_client = AsyncAnthropic(api_key=config.anthropic_api_key)
    judge = ClaudeJudge(anthropic_client, model=config.anthropic_model)
    classifier = Classifier(judge, extra_keywords=config.extra_keywords)
    moderator = Moderator(config)
    client = SpamRemoverClient(config, classifier, moderator)
    moderator.set_client(client)  # moderator needs the gateway client to resolve channels
    return client


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()
    client = build_client(config)
    client.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
