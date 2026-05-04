import os
import sqlite3
import logging
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
DB_PATH = os.getenv("DB_PATH", "/data/manage_music.db")

if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_TOKEN 環境変数を設定してください。")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("manageMusic.bot")

Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            added_by_user_id TEXT NOT NULL,
            added_by_display_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


class MusicBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Slash commands synced to guild %s", GUILD_ID)
        else:
            await self.tree.sync()
            logger.info("Slash commands synced globally (反映に最大1時間かかります)")


bot = MusicBot()


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s", bot.user)
    await bot.change_presence(activity=discord.Game(name="掃除タイムの曲を管理中"))


@bot.tree.command(name="add", description="掃除中に流す曲をキューに追加します")
@app_commands.describe(
    title="曲名",
    artist="アーティスト名",
    url="曲の URL (YouTube / Spotify など)",
)
async def add_track(
    interaction: discord.Interaction,
    title: str,
    artist: str,
    url: str,
) -> None:
    title = title.strip()
    artist = artist.strip()
    url = url.strip()

    if not (title and artist and url):
        await interaction.response.send_message(
            "❌ title / artist / url すべて指定してください。", ephemeral=True
        )
        return

    user = interaction.user
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO songs (title, artist, url, added_by_user_id, added_by_display_name)"
            " VALUES (?, ?, ?, ?, ?)",
            (title, artist, url, str(user.id), user.display_name),
        )
        conn.commit()
        logger.info("Added: %s / %s by %s", title, artist, user.display_name)
    except sqlite3.IntegrityError:
        logger.info(
            "Duplicate URL skipped: %s (requested by %s)", url, user.display_name
        )
    finally:
        conn.close()

    await interaction.response.send_message(
        f"✅ {user.display_name} さんから `{title}` / {artist} を受け付けました。"
    )


@bot.tree.command(name="queue", description="最近キューに追加された曲を表示します")
async def show_queue(interaction: discord.Interaction) -> None:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT title, artist, added_by_display_name FROM songs"
        " ORDER BY id DESC LIMIT 10"
    ).fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message(
            "🎵 まだ曲がありません。`/add` で追加してください。"
        )
        return

    lines = [
        f"{i + 1}. **{title}** / {artist}  _(by {who})_"
        for i, (title, artist, who) in enumerate(rows)
    ]
    await interaction.response.send_message(
        "🎧 最近追加された曲(最新10件):\n" + "\n".join(lines)
    )


@bot.tree.command(name="help", description="manageMusic の使い方を表示します")
async def help_command(interaction: discord.Interaction) -> None:
    embed = discord.Embed(
        title="manageMusic コマンド一覧",
        description=(
            "掃除の時間に流す曲のキューを管理するボットです。\n"
            "曲の **削除は Web UI からのみ** 行えます。"
        ),
        color=0x1DB954,
    )
    embed.add_field(
        name="/add title artist url",
        value="曲をキューに追加します。同じ URL は登録されません。",
        inline=False,
    )
    embed.add_field(
        name="/queue",
        value="最近追加された曲を最大10件表示します。",
        inline=False,
    )
    await interaction.response.send_message(embed=embed)


bot.run(DISCORD_TOKEN)
