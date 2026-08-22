"""Typed configuration loaded and validated from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_NEW_MEMBER_WINDOW_HOURS = 48


class ConfigError(ValueError):
    """Raised when required configuration is missing or malformed."""


def _parse_id_list(raw: str | None) -> frozenset[int]:
    """Parse a comma-separated list of Discord snowflake IDs into ints."""
    if not raw:
        return frozenset()
    ids: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.add(int(chunk))
        except ValueError as exc:
            raise ConfigError(f"Invalid Discord ID {chunk!r}: expected a number") from exc
    return frozenset(ids)


def _parse_keywords(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(k.strip().lower() for k in raw.split(",") if k.strip())


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    """All runtime settings for the bot."""

    discord_token: str
    anthropic_api_key: str
    officer_channel_id: int
    new_member_window_hours: int = DEFAULT_NEW_MEMBER_WINDOW_HOURS
    trusted_role_ids: frozenset[int] = field(default_factory=frozenset)
    monitored_channel_ids: frozenset[int] = field(default_factory=frozenset)
    extra_keywords: tuple[str, ...] = ()
    dry_run: bool = True
    anthropic_model: str = DEFAULT_MODEL

    @classmethod
    def from_env(cls, *, load_dotenv_file: bool = True) -> "Config":
        """Build a Config from environment variables, validating required fields."""
        if load_dotenv_file:
            load_dotenv()

        token = (os.getenv("DISCORD_TOKEN") or "").strip()
        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        officer_channel_raw = (os.getenv("OFFICER_CHANNEL_ID") or "").strip()

        missing = [
            name
            for name, value in (
                ("DISCORD_TOKEN", token),
                ("ANTHROPIC_API_KEY", api_key),
                ("OFFICER_CHANNEL_ID", officer_channel_raw),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing required environment variables: " + ", ".join(missing)
            )

        try:
            officer_channel_id = int(officer_channel_raw)
        except ValueError as exc:
            raise ConfigError("OFFICER_CHANNEL_ID must be a number") from exc

        window_raw = (os.getenv("NEW_MEMBER_WINDOW_HOURS") or "").strip()
        try:
            window = int(window_raw) if window_raw else DEFAULT_NEW_MEMBER_WINDOW_HOURS
        except ValueError as exc:
            raise ConfigError("NEW_MEMBER_WINDOW_HOURS must be a number") from exc
        if window <= 0:
            raise ConfigError("NEW_MEMBER_WINDOW_HOURS must be positive")

        return cls(
            discord_token=token,
            anthropic_api_key=api_key,
            officer_channel_id=officer_channel_id,
            new_member_window_hours=window,
            trusted_role_ids=_parse_id_list(os.getenv("TRUSTED_ROLE_IDS")),
            monitored_channel_ids=_parse_id_list(os.getenv("MONITORED_CHANNEL_IDS")),
            extra_keywords=_parse_keywords(os.getenv("SPAM_KEYWORDS")),
            dry_run=_parse_bool(os.getenv("DRY_RUN"), default=True),
            anthropic_model=(os.getenv("ANTHROPIC_MODEL") or DEFAULT_MODEL).strip(),
        )
