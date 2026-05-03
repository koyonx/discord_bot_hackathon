from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    discord_token: str
    discord_guild_id: int | None
    workspace_root: str
    check_timeout_seconds: float
    total_timeout_seconds: float


def _env(name: str, default: str = "") -> str:
    """Read an env var, treating empty/whitespace-only values as unset.

    docker-compose's env_file injects keys with empty values verbatim, so
    `REVIEW_CHECK_TIMEOUT_SECONDS=` in .env would otherwise yield "" and break
    float() coercion below.
    """
    value = os.environ.get(name, "").strip()
    return value if value else default


def load_config() -> Config:
    token = _env("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required")

    guild_id_raw = _env("DISCORD_GUILD_ID")
    guild_id = int(guild_id_raw) if guild_id_raw else None

    return Config(
        discord_token=token,
        discord_guild_id=guild_id,
        workspace_root=_env("REVIEW_WORKSPACE_ROOT", "/var/tmp/prereview"),
        check_timeout_seconds=float(_env("REVIEW_CHECK_TIMEOUT_SECONDS", "120")),
        total_timeout_seconds=float(_env("REVIEW_TOTAL_TIMEOUT_SECONDS", "600")),
    )
