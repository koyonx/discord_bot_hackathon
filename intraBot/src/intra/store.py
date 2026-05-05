from __future__ import annotations

import os
import time
from dataclasses import dataclass

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    discord_id TEXT PRIMARY KEY,
    intra_login TEXT NOT NULL,
    intra_user_id INTEGER NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expires_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_login ON users(intra_login);

CREATE TABLE IF NOT EXISTS oauth_states (
    state TEXT PRIMARY KEY,
    discord_id TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS notify_seen (
    discord_id TEXT NOT NULL,
    scale_team_id INTEGER NOT NULL,
    seen_at INTEGER NOT NULL,
    PRIMARY KEY (discord_id, scale_team_id)
);
"""


@dataclass
class LinkedUser:
    discord_id: str
    intra_login: str
    intra_user_id: int
    access_token: str
    refresh_token: str
    token_expires_at: int


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    # ----- oauth_states -----
    async def put_state(self, state: str, discord_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO oauth_states (state, discord_id, created_at) VALUES (?, ?, ?)",
                (state, discord_id, int(time.time())),
            )
            await db.commit()

    async def pop_state(self, state: str, max_age_sec: int = 600) -> str | None:
        """Return discord_id if state is valid and unexpired, else None. Also deletes the state."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT discord_id, created_at FROM oauth_states WHERE state = ?",
                (state,),
            ) as cur:
                row = await cur.fetchone()
            if row is None:
                return None
            await db.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
            await db.commit()
            discord_id, created_at = row
            if int(time.time()) - int(created_at) > max_age_sec:
                return None
            return discord_id

    # ----- users -----
    async def upsert_user(
        self,
        discord_id: str,
        intra_login: str,
        intra_user_id: int,
        access_token: str,
        refresh_token: str,
        token_expires_at: int,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO users (discord_id, intra_login, intra_user_id, access_token, refresh_token, token_expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(discord_id) DO UPDATE SET
                    intra_login=excluded.intra_login,
                    intra_user_id=excluded.intra_user_id,
                    access_token=excluded.access_token,
                    refresh_token=excluded.refresh_token,
                    token_expires_at=excluded.token_expires_at,
                    updated_at=excluded.updated_at
                """,
                (
                    discord_id,
                    intra_login,
                    intra_user_id,
                    access_token,
                    refresh_token,
                    token_expires_at,
                    int(time.time()),
                ),
            )
            await db.commit()

    async def update_tokens(
        self,
        discord_id: str,
        access_token: str,
        refresh_token: str,
        token_expires_at: int,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE users SET access_token = ?, refresh_token = ?, token_expires_at = ?, updated_at = ?
                WHERE discord_id = ?
                """,
                (access_token, refresh_token, token_expires_at, int(time.time()), discord_id),
            )
            await db.commit()

    async def get_by_discord(self, discord_id: str) -> LinkedUser | None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT discord_id, intra_login, intra_user_id, access_token, refresh_token, token_expires_at FROM users WHERE discord_id = ?",
                (discord_id,),
            ) as cur:
                row = await cur.fetchone()
        return LinkedUser(*row) if row else None

    async def get_by_login(self, login: str) -> LinkedUser | None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT discord_id, intra_login, intra_user_id, access_token, refresh_token, token_expires_at FROM users WHERE intra_login = ?",
                (login,),
            ) as cur:
                row = await cur.fetchone()
        return LinkedUser(*row) if row else None

    async def all_linked(self) -> list[LinkedUser]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT discord_id, intra_login, intra_user_id, access_token, refresh_token, token_expires_at FROM users"
            ) as cur:
                rows = await cur.fetchall()
        return [LinkedUser(*r) for r in rows]

    # ----- notify_seen -----
    async def is_notify_seen(self, discord_id: str, scale_team_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM notify_seen WHERE discord_id = ? AND scale_team_id = ?",
                (discord_id, scale_team_id),
            ) as cur:
                return (await cur.fetchone()) is not None

    async def mark_notify_seen(self, discord_id: str, scale_team_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO notify_seen (discord_id, scale_team_id, seen_at) VALUES (?, ?, ?)",
                (discord_id, scale_team_id, int(time.time())),
            )
            await db.commit()
