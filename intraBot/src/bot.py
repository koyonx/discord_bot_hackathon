from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

# `src/` をパスに入れる (Docker でも host でも動くように)
sys.path.insert(0, str(Path(__file__).parent))

from intra.client import IntraClient
from intra.oauth import OAuthServer
from intra.store import Store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("intraBot")


COG_MODULES = [
    "cogs.link",
    "cogs.status",
    "cogs.slot",
    "cogs.finder",
    "cogs.online",
    "cogs.notify",
    "cogs.welcome",
    "cogs.help",
    "cogs.freeze_guide",
    "cogs.follow",
    "cogs.find_evaluator",
    "cogs.events",
    "cogs.project",
    "cogs.reviews",
]


class IntraBot(commands.Bot):
    def __init__(
        self,
        *,
        store: Store,
        client: IntraClient,
        oauth: OAuthServer,
        guild_id: int,
        welcome_channel_id: int | None,
        campus_name: str,
        notify_poll_seconds: int,
    ):
        intents = discord.Intents.default()
        intents.members = True  # welcome (Server Members Intent)
        # message_content intent を持たないので prefix を when_mentioned にして警告抑止 (slash 専用運用)
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.store = store
        self.client = client
        self.oauth = oauth
        self.guild_id = guild_id
        self.welcome_channel_id = welcome_channel_id
        self.campus_name = campus_name
        self.notify_poll_seconds = notify_poll_seconds
        self.campus_id: int = 0

    async def setup_hook(self) -> None:
        # campus 解決
        try:
            self.campus_id = await self.client.resolve_campus_id(self.campus_name)
            log.info("resolved campus_id=%d (%s)", self.campus_id, self.campus_name)
        except Exception:
            log.exception("campus resolution failed; defaulting to Tokyo (26)")
            self.campus_id = 26

        # cog ロード
        for mod in COG_MODULES:
            await self.load_extension(mod)
            log.info("loaded cog: %s", mod)

        # guild 即時同期
        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        log.info("slash commands synced to guild %d (%d cmds)", self.guild_id, len(synced))

    async def on_ready(self) -> None:
        log.info("Discord bot logged in as %s (id=%s)", self.user, self.user.id if self.user else "?")


async def main() -> None:
    load_dotenv()

    discord_token = _required("DISCORD_TOKEN")
    guild_id = int(_required("DISCORD_GUILD_ID"))
    welcome_channel_id = _opt_int("DISCORD_WELCOME_CHANNEL_ID")
    intra_uid = _required("INTRA_UID")
    intra_secret = _required("INTRA_SECRET")
    redirect_uri = _required("INTRA_REDIRECT_URI")
    api_base = os.getenv("INTRA_API_BASE", "https://api.intra.42.fr")
    campus_name = os.getenv("INTRA_CAMPUS_NAME", "Tokyo")
    db_path = os.getenv("DB_PATH", "/data/intrabot.sqlite")
    callback_host = os.getenv("OAUTH_CALLBACK_HOST", "0.0.0.0")
    callback_port = int(os.getenv("OAUTH_CALLBACK_PORT", "4242"))
    notify_poll_seconds = int(os.getenv("NOTIFY_POLL_SECONDS", "60"))

    store = Store(db_path)
    await store.init()
    log.info("store initialized at %s", db_path)

    client = IntraClient(api_base, intra_uid, intra_secret, redirect_uri)
    await client.__aenter__()
    try:
        # OAuth callback サーバーが Discord ユーザーに DM 送る用のフック
        bot_holder: dict = {}

        async def on_link(discord_id: str, intra_login: str) -> None:
            bot = bot_holder.get("bot")
            if bot is None:
                return
            try:
                user = await bot.fetch_user(int(discord_id))
                await user.send(f"✅ 紐付け完了 (login: `{intra_login}`)")
            except Exception:
                log.exception("on_link DM failed")

        oauth = OAuthServer(store, client, on_link, callback_host, callback_port)
        await oauth.start()

        bot = IntraBot(
            store=store,
            client=client,
            oauth=oauth,
            guild_id=guild_id,
            welcome_channel_id=welcome_channel_id,
            campus_name=campus_name,
            notify_poll_seconds=notify_poll_seconds,
        )
        bot_holder["bot"] = bot

        try:
            await bot.start(discord_token)
        finally:
            await bot.close()
            await oauth.stop()
    finally:
        await client.__aexit__(None, None, None)


def _required(key: str) -> str:
    v = os.getenv(key)
    if not v:
        raise SystemExit(f"環境変数 {key} が未設定です。intraBot/.env を確認してください。")
    return v


def _opt_int(key: str) -> int | None:
    v = os.getenv(key)
    return int(v) if v else None


if __name__ == "__main__":
    asyncio.run(main())
