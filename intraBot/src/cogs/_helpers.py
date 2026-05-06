from __future__ import annotations

import time

from intra.client import IntraClient
from intra.store import LinkedUser, Store


class NotLinkedError(Exception):
    pass


async def get_valid_user_token(store: Store, client: IntraClient, discord_id: str) -> tuple[LinkedUser, str]:
    """Return (user, access_token), refreshing the OAuth token if it's about to expire."""
    user = await store.get_by_discord(discord_id)
    if user is None:
        raise NotLinkedError()
    if user.token_expires_at - int(time.time()) >= 60:
        return user, user.access_token

    tok = await client.refresh_user_token(user.refresh_token)
    access = tok["access_token"]
    refresh = tok.get("refresh_token", user.refresh_token)
    expires_at = int(time.time()) + int(tok.get("expires_in", 7200))
    await store.update_tokens(discord_id, access, refresh, expires_at)
    user.access_token = access
    user.refresh_token = refresh
    user.token_expires_at = expires_at
    return user, access


def cursus_pick_main(cursus_users: list[dict]) -> dict | None:
    """関連する cursus_users エントリを 1 つ選ぶ。

    優先順:
      1. cursus.id == 21 (42cursus)
      2. その中で end_at が無い (= 在籍中) もの
      3. begin_at が新しいもの

    こうしないと、BH'd になって離脱した古い 42cursus エントリの blackholed_at を拾い、
    現在は別の cursus に居る人の表示がおかしくなる。
    """
    if not cursus_users:
        return None

    pool_21 = [cu for cu in cursus_users if (cu.get("cursus") or {}).get("id") == 21]
    pool = pool_21 if pool_21 else cursus_users

    active = [cu for cu in pool if not cu.get("end_at")]
    if active:
        return sorted(active, key=lambda c: c.get("begin_at") or "", reverse=True)[0]

    return sorted(pool, key=lambda c: c.get("begin_at") or "", reverse=True)[0]


def truncate(s: str, n: int = 1000) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"
