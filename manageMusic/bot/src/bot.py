import hashlib
import logging
import os
import sqlite3
import uuid
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
DB_PATH = os.getenv("DB_PATH", "/data/manage_music.db")
MAX_FILE_SIZE_MB_RAW = os.getenv("MAX_FILE_SIZE_MB", "").strip()

if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_TOKEN 環境変数を設定してください。")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("manageMusic.bot")

DATA_DIR = Path(DB_PATH).parent
FILES_DIR = DATA_DIR / "files"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "mp3", "m4a", "aac", "wav", "flac", "ogg", "opus",
    "mp4", "webm", "mov",
}


def _parse_max_size_bytes(value: str) -> int | None:
    if not value:
        return None
    try:
        mb = float(value)
    except ValueError:
        logger.warning("MAX_FILE_SIZE_MB invalid: %r — ignored", value)
        return None
    if mb <= 0:
        return None
    return int(mb * 1024 * 1024)


MAX_FILE_SIZE_BYTES = _parse_max_size_bytes(MAX_FILE_SIZE_MB_RAW)


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Music (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            url TEXT NOT NULL,
            file_hash TEXT,
            added_by_user_id TEXT NOT NULL,
            added_by_display_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_music_url ON Music(url)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_music_file_hash"
        " ON Music(file_hash) WHERE file_hash IS NOT NULL"
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
            logger.info("Slash commands synced globally (反映に最大1時間)")


bot = MusicBot()


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s", bot.user)
    await bot.change_presence(activity=discord.Game(name="掃除タイムの曲を管理中"))


music_group = app_commands.Group(
    name="music",
    description="掃除タイム用プレイリストを管理します",
)


def _insert_music(
    title: str,
    artist: str,
    url: str,
    file_hash: str | None,
    user: discord.abc.User,
) -> str:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO Music (title, artist, url, file_hash,"
            " added_by_user_id, added_by_display_name)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (title, artist, url, file_hash, str(user.id), user.display_name),
        )
        conn.commit()
        return "inserted"
    except sqlite3.IntegrityError:
        return "duplicate"
    finally:
        conn.close()


def _file_hash_exists(file_hash: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT 1 FROM Music WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


@music_group.command(
    name="add",
    description="プレイリストに曲を追加します (URL またはファイル添付)",
)
@app_commands.describe(
    title="曲名",
    artist="アーティスト名",
    url="曲の URL (YouTube / Spotify など)",
    file="音声/動画ファイル (mp3, m4a, wav, mp4 など)",
)
async def music_add(
    interaction: discord.Interaction,
    title: str,
    artist: str,
    url: str | None = None,
    file: discord.Attachment | None = None,
) -> None:
    title = title.strip()
    artist = artist.strip()

    if not title or not artist:
        await interaction.response.send_message(
            "❌ title と artist は必須です。", ephemeral=True
        )
        return

    if (url is None) == (file is None):
        await interaction.response.send_message(
            "❌ url または file のどちらか一方を指定してください。",
            ephemeral=True,
        )
        return

    user = interaction.user

    if file is not None:
        ext = (
            file.filename.rsplit(".", 1)[-1].lower()
            if "." in file.filename
            else ""
        )
        if ext not in ALLOWED_EXTENSIONS:
            await interaction.response.send_message(
                f"❌ 拡張子 .{ext or '?'} は許可されていません。"
                f" 許可: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                ephemeral=True,
            )
            return

        if MAX_FILE_SIZE_BYTES and file.size > MAX_FILE_SIZE_BYTES:
            limit_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
            await interaction.response.send_message(
                f"❌ ファイルサイズが上限 {limit_mb:.1f}MB を超えています"
                f" (今回 {file.size / (1024 * 1024):.1f}MB)。",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        data = await file.read()
        file_hash = hashlib.sha256(data).hexdigest()

        if _file_hash_exists(file_hash):
            logger.info(
                "Duplicate file skipped (hash=%s) by %s",
                file_hash, user.display_name,
            )
        else:
            saved_name = f"{uuid.uuid4().hex}.{ext}"
            saved_path = FILES_DIR / saved_name
            saved_path.write_bytes(data)
            stored_url = f"/files/{saved_name}"
            result = _insert_music(title, artist, stored_url, file_hash, user)
            if result == "duplicate":
                saved_path.unlink(missing_ok=True)
                logger.info(
                    "Race-condition duplicate (hash=%s) — file removed",
                    file_hash,
                )
            else:
                logger.info(
                    "Added file: %s / %s by %s (%s)",
                    title, artist, user.display_name, saved_name,
                )

        await interaction.followup.send(
            f"✅ {user.display_name} さんから `{title}` / {artist} を受け付けました。"
        )
        return

    url_value = (url or "").strip()
    if not url_value:
        await interaction.response.send_message(
            "❌ url が空です。", ephemeral=True
        )
        return

    result = _insert_music(title, artist, url_value, None, user)
    if result == "duplicate":
        logger.info(
            "Duplicate URL skipped: %s by %s", url_value, user.display_name
        )
    else:
        logger.info(
            "Added URL: %s / %s by %s", title, artist, user.display_name
        )

    await interaction.response.send_message(
        f"✅ {user.display_name} さんから `{title}` / {artist} を受け付けました。"
    )


@music_group.command(
    name="queue",
    description="最近追加された曲を最大10件表示します",
)
async def music_queue(interaction: discord.Interaction) -> None:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT title, artist, added_by_display_name FROM Music"
        " ORDER BY id DESC LIMIT 10"
    ).fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message(
            "🎵 まだ曲がありません。`/music add` で追加してください。"
        )
        return

    lines = [
        f"{i + 1}. **{title}** / {artist}  _(by {who})_"
        for i, (title, artist, who) in enumerate(rows)
    ]
    await interaction.response.send_message(
        "🎧 最近追加された曲(最新10件):\n" + "\n".join(lines)
    )


@music_group.command(
    name="help",
    description="manageMusic の使い方を表示します",
)
async def music_help(interaction: discord.Interaction) -> None:
    embed = discord.Embed(
        title="manageMusic コマンド一覧",
        description=(
            "掃除の時間に流す曲のキューを管理するボットです。\n"
            "曲の **削除は Web UI からのみ** 行えます。"
        ),
        color=0x1DB954,
    )
    embed.add_field(
        name="/music add title artist [url] [file]",
        value=(
            "曲を追加します。`url` または `file` のどちらかを指定してください。\n"
            "対応拡張子: " + ", ".join(sorted(ALLOWED_EXTENSIONS))
        ),
        inline=False,
    )
    embed.add_field(
        name="/music queue",
        value="最近追加された曲を最大10件表示します。",
        inline=False,
    )
    await interaction.response.send_message(embed=embed)


bot.tree.add_command(music_group)


bot.run(DISCORD_TOKEN)
