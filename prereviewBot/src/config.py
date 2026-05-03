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


def load_config() -> Config:
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required")

    guild_id_raw = os.environ.get("DISCORD_GUILD_ID", "").strip()
    guild_id = int(guild_id_raw) if guild_id_raw else None

    return Config(
        discord_token=token,
        discord_guild_id=guild_id,
        workspace_root=os.environ.get("REVIEW_WORKSPACE_ROOT", "/var/tmp/prereview"),
        check_timeout_seconds=float(os.environ.get("REVIEW_CHECK_TIMEOUT_SECONDS", "120")),
        total_timeout_seconds=float(os.environ.get("REVIEW_TOTAL_TIMEOUT_SECONDS", "600")),
    )
