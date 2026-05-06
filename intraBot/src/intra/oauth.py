from __future__ import annotations

import logging
import secrets
import time
from typing import Awaitable, Callable

from aiohttp import web

from .client import IntraClient
from .store import Store

log = logging.getLogger("intraBot.oauth")

OnLink = Callable[[str, str], Awaitable[None]]  # (discord_id, intra_login) -> None


class OAuthServer:
    """Tiny aiohttp server that handles the 42 OAuth2 redirect.

    Flow:
      1. /link cog calls `make_authorize_url(discord_id)` to get a state-bound URL.
      2. User opens URL, authorizes on intra, intra redirects to /callback.
      3. /callback exchanges code -> tokens, fetches /v2/me, persists, then notifies
         the bot via the on_link callback so a DM can be sent.
    """

    def __init__(self, store: Store, client: IntraClient, on_link: OnLink, host: str, port: int):
        self.store = store
        self.client = client
        self.on_link = on_link
        self.host = host
        self.port = port
        self._runner: web.AppRunner | None = None

    async def make_authorize_url(self, discord_id: str) -> str:
        state = secrets.token_urlsafe(24)
        await self.store.put_state(state, discord_id)
        return self.client.authorize_url(state)

    async def start(self) -> None:
        app = web.Application()
        app.add_routes([web.get("/callback", self._handle_callback), web.get("/", self._handle_root)])
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        log.info("OAuth callback server listening on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _handle_root(self, _req: web.Request) -> web.Response:
        return web.Response(text="intraBot OAuth callback server is up.")

    async def _handle_callback(self, req: web.Request) -> web.Response:
        if "error" in req.query:
            return _html("認可がキャンセルされました", req.query.get("error_description", req.query["error"]), ok=False)
        code = req.query.get("code")
        state = req.query.get("state")
        if not code or not state:
            return _html("不正なコールバック", "code または state が見つかりません。", ok=False)

        discord_id = await self.store.pop_state(state)
        if not discord_id:
            return _html("state エラー", "state が見つからないか期限切れです。`/link` を再実行してください。", ok=False)

        try:
            tok = await self.client.exchange_code(code)
        except Exception as e:
            log.exception("token exchange failed")
            return _html("トークン交換に失敗", str(e), ok=False)

        access = tok["access_token"]
        refresh = tok.get("refresh_token", "")
        expires_at = int(time.time()) + int(tok.get("expires_in", 7200))

        try:
            me = await self.client.get_me(access)
        except Exception as e:
            log.exception("/v2/me failed")
            return _html("ユーザー情報取得に失敗", str(e), ok=False)

        login = me["login"]
        intra_user_id = int(me["id"])
        await self.store.upsert_user(discord_id, login, intra_user_id, access, refresh, expires_at)

        try:
            await self.on_link(discord_id, login)
        except Exception:
            log.exception("on_link callback failed (link itself succeeded)")

        return _html("✅ 紐付け完了", f"42 login: <b>{login}</b><br>このタブは閉じて Discord に戻ってください。", ok=True)


def _html(title: str, body: str, *, ok: bool) -> web.Response:
    color = "#2ecc71" if ok else "#e74c3c"
    page = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>intraBot</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; background: #1e1f22; color: #ddd; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
.card {{ background: #2b2d31; border-radius: 12px; padding: 32px 40px; max-width: 480px; box-shadow: 0 4px 20px rgba(0,0,0,.3); border-left: 4px solid {color}; }}
h1 {{ margin: 0 0 12px; font-size: 1.4em; }}
p {{ margin: 0; line-height: 1.5; }}
</style></head>
<body><div class="card"><h1>{title}</h1><p>{body}</p></div></body></html>
"""
    status = 200 if ok else 400
    return web.Response(text=page, content_type="text/html", status=status)
