from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp

log = logging.getLogger("intraBot.client")

DEFAULT_SCOPES = "public profile projects"


class IntraError(Exception):
    def __init__(self, status: int, message: str, body: Any = None):
        super().__init__(f"[{status}] {message}")
        self.status = status
        self.body = body


class IntraClient:
    """Wrapper around the 42 intra v2 API.

    - App token (client_credentials) is cached and auto-refreshed.
    - User tokens are passed in by callers; refresh_user_token() rotates them.
    - Concurrency limited to ~2 req/sec to stay under the documented rate limit.
    """

    def __init__(self, base: str, uid: str, secret: str, redirect_uri: str):
        self.base = base.rstrip("/")
        self.uid = uid
        self.secret = secret
        self.redirect_uri = redirect_uri
        self._session: aiohttp.ClientSession | None = None
        self._app_token: str | None = None
        self._app_token_expires_at: int = 0
        self._sem = asyncio.Semaphore(2)
        self._last_call = 0.0

    async def __aenter__(self) -> "IntraClient":
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self

    async def __aexit__(self, *exc) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("IntraClient must be used as async context manager")
        return self._session

    # ===== OAuth helpers =====

    def authorize_url(self, state: str, scopes: str = DEFAULT_SCOPES) -> str:
        params = {
            "client_id": self.uid,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scopes,
            "state": state,
        }
        return f"{self.base}/oauth/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        data = {
            "grant_type": "authorization_code",
            "client_id": self.uid,
            "client_secret": self.secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        return await self._post_form("/oauth/token", data)

    async def refresh_user_token(self, refresh_token: str) -> dict[str, Any]:
        data = {
            "grant_type": "refresh_token",
            "client_id": self.uid,
            "client_secret": self.secret,
            "refresh_token": refresh_token,
        }
        return await self._post_form("/oauth/token", data)

    async def _get_app_token(self) -> str:
        now = int(time.time())
        if self._app_token and now < self._app_token_expires_at - 60:
            return self._app_token
        data = {
            "grant_type": "client_credentials",
            "client_id": self.uid,
            "client_secret": self.secret,
        }
        body = await self._post_form("/oauth/token", data)
        self._app_token = body["access_token"]
        self._app_token_expires_at = now + int(body.get("expires_in", 7200))
        return self._app_token

    # ===== Low-level HTTP =====

    async def _throttle(self) -> None:
        # ~2 req/sec. Crude but simple.
        async with self._sem:
            elapsed = time.monotonic() - self._last_call
            if elapsed < 0.5:
                await asyncio.sleep(0.5 - elapsed)
            self._last_call = time.monotonic()

    async def _post_form(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        await self._throttle()
        async with self.session.post(self.base + path, data=data) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                raise IntraError(resp.status, body.get("error_description") or body.get("error") or "request failed", body)
            return body

    async def _get(self, path: str, *, token: str | None = None, params: dict | None = None) -> Any:
        if token is None:
            token = await self._get_app_token()
        await self._throttle()
        url = self.base + path
        headers = {"Authorization": f"Bearer {token}"}
        for attempt in range(3):
            async with self.session.get(url, headers=headers, params=params) as resp:
                if resp.status == 429:
                    await asyncio.sleep(1 + attempt)
                    continue
                body = await resp.json(content_type=None)
                if resp.status >= 400:
                    msg = body.get("error") or body.get("message") or "request failed"
                    if isinstance(body, dict) and body.get("errors"):
                        msg = f"{msg} — {body['errors']}"
                    raise IntraError(resp.status, _truncate(msg), body)
                return body
        raise IntraError(429, "rate limited after retries")

    async def _request(self, method: str, path: str, *, token: str, json: Any = None, params: dict | None = None) -> Any:
        await self._throttle()
        url = self.base + path
        headers = {"Authorization": f"Bearer {token}"}
        async with self.session.request(method, url, headers=headers, json=json, params=params) as resp:
            text = await resp.text()
            if resp.status == 204 or not text:
                return None
            try:
                body = await resp.json(content_type=None) if text else None
            except Exception:
                log.warning("non-JSON body for %s %s (status=%s): %s", method, path, resp.status, text[:200])
                body = {"raw": text}
            if resp.status >= 400:
                msg = (body.get("message") or body.get("error") or text) if isinstance(body, dict) else text
                raise IntraError(resp.status, _truncate(msg), body)
            return body

    async def _paginate(self, path: str, *, params: dict | None = None, max_pages: int = 20) -> list[dict]:
        out: list[dict] = []
        params = dict(params or {})
        params.setdefault("page[size]", 100)
        for page in range(1, max_pages + 1):
            params["page[number]"] = page
            chunk = await self._get(path, params=params)
            if not chunk:
                break
            out.extend(chunk)
            if len(chunk) < int(params["page[size]"]):
                break
        return out

    # ===== Users =====

    async def get_user(self, login_or_id: str | int) -> dict:
        return await self._get(f"/v2/users/{login_or_id}")

    async def get_me(self, user_token: str) -> dict:
        return await self._get("/v2/me", token=user_token)

    async def get_cursus_users(self, user_id: int) -> list[dict]:
        return await self._paginate(f"/v2/users/{user_id}/cursus_users")

    async def get_projects_users(self, user_id: int) -> list[dict]:
        return await self._paginate(f"/v2/users/{user_id}/projects_users")

    async def get_user_active_location(self, user_id: int) -> dict | None:
        rows = await self._get(
            f"/v2/users/{user_id}/locations",
            params={"filter[active]": "true", "page[size]": 1},
        )
        return rows[0] if rows else None

    async def get_user_last_location(self, user_id: int) -> dict | None:
        rows = await self._get(
            f"/v2/users/{user_id}/locations",
            params={"sort": "-end_at", "page[size]": 1},
        )
        return rows[0] if rows else None

    async def get_user_closes(self, user_id: int) -> list[dict]:
        return await self._paginate(f"/v2/users/{user_id}/closes")

    async def get_user_scale_teams(self, user_id: int, since_iso: str | None = None) -> list[dict]:
        params: dict[str, Any] = {"sort": "-begin_at"}
        if since_iso:
            params["range[begin_at]"] = f"{since_iso},{_now_iso()}"
        return await self._paginate(f"/v2/users/{user_id}/scale_teams", params=params)

    # ===== Campus / projects =====

    async def resolve_campus_id(self, name: str) -> int:
        rows = await self._get("/v2/campus", params={"filter[name]": name, "page[size]": 100})
        for r in rows:
            if r.get("name", "").lower() == name.lower():
                return int(r["id"])
        raise IntraError(404, f"campus '{name}' not found")

    async def get_campus_active_locations(self, campus_id: int) -> list[dict]:
        return await self._paginate(
            f"/v2/campus/{campus_id}/locations",
            params={"filter[active]": "true"},
        )

    async def get_campus_events(self, campus_id: int) -> list[dict]:
        """campus のイベント一覧 (過去〜未来全部)。クライアント側で絞る前提。"""
        return await self._paginate(
            f"/v2/campus/{campus_id}/events",
            params={"sort": "-begin_at"},
            max_pages=5,
        )

    async def get_event(self, event_id: int) -> dict:
        return await self._get(f"/v2/events/{event_id}")

    async def get_event_users(self, event_id: int) -> list[dict]:
        """event の参加者一覧 (events_users)."""
        return await self._paginate(f"/v2/events/{event_id}/events_users", max_pages=10)

    # ----- exams (events と別エンドポイント) -----

    async def get_campus_exams(self, campus_id: int) -> list[dict]:
        """campus の exams 一覧。"""
        return await self._paginate(
            f"/v2/campus/{campus_id}/exams",
            params={"sort": "-begin_at"},
            max_pages=5,
        )

    async def get_exam(self, exam_id: int) -> dict:
        return await self._get(f"/v2/exams/{exam_id}")

    async def get_exam_users(self, exam_id: int) -> list[dict]:
        """exam の参加者一覧 (exams_users)."""
        return await self._paginate(f"/v2/exams/{exam_id}/exams_users", max_pages=10)

    async def register_exam(self, user_token: str, exam_id: int) -> dict:
        """exam に参加登録 (本人 OAuth)."""
        body = {"exams_user": {"exam_id": exam_id}}
        return await self._request("POST", "/v2/exams_users", token=user_token, json=body)

    async def find_user_exam_registration(
        self, user_token: str, user_id: int, exam_id: int
    ) -> dict | None:
        rows = await self._request(
            "GET",
            f"/v2/users/{user_id}/exams_users",
            token=user_token,
            params={"filter[exam_id]": exam_id},
        )
        if isinstance(rows, list) and rows:
            return rows[0]
        return None

    async def leave_exam(self, user_token: str, exams_user_id: int) -> None:
        await self._request("DELETE", f"/v2/exams_users/{exams_user_id}", token=user_token)

    async def register_event(self, user_token: str, event_id: int) -> dict:
        """イベントに参加登録 (本人 OAuth トークン必須)."""
        body = {"events_user": {"event_id": event_id}}
        return await self._request("POST", "/v2/events_users", token=user_token, json=body)

    async def find_user_event_registration(
        self, user_token: str, user_id: int, event_id: int
    ) -> dict | None:
        """指定 event の自分の events_user を返す。未登録なら None."""
        rows = await self._request(
            "GET",
            f"/v2/users/{user_id}/events_users",
            token=user_token,
            params={"filter[event_id]": event_id},
        )
        if isinstance(rows, list) and rows:
            return rows[0]
        return None

    async def leave_event(self, user_token: str, events_user_id: int) -> None:
        """イベント参加を取り消し (events_user id を指定)."""
        await self._request(
            "DELETE", f"/v2/events_users/{events_user_id}", token=user_token
        )

    async def get_campus_users(
        self,
        campus_id: int,
        *,
        pool_year: int | None = None,
        pool_month: str | None = None,
    ) -> list[dict]:
        """campus に紐づく cadet を pool_year / pool_month で絞って取得。"""
        params: dict[str, Any] = {}
        if pool_year is not None:
            params["filter[pool_year]"] = pool_year
        if pool_month:
            params["filter[pool_month]"] = pool_month.lower()
        return await self._paginate(f"/v2/campus/{campus_id}/users", params=params)

    async def get_cursus_projects(self, cursus_id: int = 21) -> list[dict]:
        """指定 cursus の project 一覧 (42cursus = 21)。

        ページ数は最大 5 (=500 件) に絞って起動を速く保つ。autocomplete 候補に十分。
        """
        return await self._paginate(f"/v2/cursus/{cursus_id}/projects", max_pages=5)

    async def find_project(self, name_or_slug: str) -> dict | None:
        """name または slug が **完全一致** する project を返す。無ければ None。

        autocomplete からは slug 形式 (`cpp-module-03`) で渡ってくるので
        slug filter を先に試し、ダメなら name filter で再試行する。
        """
        nl = name_or_slug.lower().strip()

        # 1. slug で引く
        try:
            rows = await self._get(
                "/v2/projects",
                params={"filter[slug]": nl, "page[size]": 5},
            )
            for r in rows:
                if (r.get("slug") or "").lower() == nl:
                    return r
        except IntraError as e:
            log.warning("find_project: filter[slug] rejected (%s), falling back to filter[name]", e)

        # 2. name で引く
        rows = await self._get(
            "/v2/projects",
            params={"filter[name]": name_or_slug, "page[size]": 5},
        )
        for r in rows:
            if (r.get("name") or "").lower() == nl or (r.get("slug") or "").lower() == nl:
                return r
        return None

    async def get_project_validated_users(self, project_id: int, campus_id: int | None = None) -> list[dict]:
        """validated (合格) な projects_users を返す。

        42 API では `validated` フィルタは存在しないため、サーバー側で
        `filter[marked]=true` で採点済みに絞り、クライアント側で
        `validated?` フラグを見て合格者だけ残す。campus フィルタのキーは
        `filter[campus]` (※ campus_id では無い)。
        """
        params: dict[str, Any] = {"filter[marked]": "true"}
        if campus_id is not None:
            params["filter[campus]"] = campus_id
        rows = await self._paginate(f"/v2/projects/{project_id}/projects_users", params=params)
        return [r for r in rows if r.get("validated?")]

    # ===== Slots (user-token actions) =====

    async def list_user_slots(self, user_token: str) -> list[dict]:
        return await self._request("GET", "/v2/me/slots", token=user_token)

    async def create_slot(
        self,
        user_token: str,
        user_id: int,
        begin_at_iso: str,
        end_at_iso: str,
    ) -> dict:
        """slot を作成。

        42 API doc によれば body に `user_ids` (array) を付け、その値は
        OAuth token の owner と一致させる必要がある。15 分粒度に丸められ、
        duration が 15 分超なら複数の slot に分割される。
        """
        body = {
            "slot": {
                "user_ids": [user_id],
                "begin_at": begin_at_iso,
                "end_at": end_at_iso,
            }
        }
        return await self._request("POST", "/v2/slots", token=user_token, json=body)

    async def delete_slot(self, user_token: str, slot_id: int) -> None:
        await self._request("DELETE", f"/v2/slots/{slot_id}", token=user_token)



def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _truncate(s: Any, n: int = 300) -> str:
    """API エラーメッセージが HTML / 巨大文字列のときに Discord (2000 字) に収まるよう短縮。"""
    if not isinstance(s, str):
        s = str(s)
    s = s.strip()
    return s if len(s) <= n else s[:n] + "..."
