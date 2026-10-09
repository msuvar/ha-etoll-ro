"""Async client for the eToll România (TollRo) portal.

Authentication mirrors what the official web portal does: an OpenID Connect
authorization-code flow with PKCE against Keycloak (sso.etoll.ro, realm
"external", public client "ddcm-authz-client"). The username/password form is
submitted directly, the authorization code is captured from the redirect and
exchanged for tokens. Afterwards the refresh token is used; if it has expired
(the realm gives ~60 minutes) the integration logs in again.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import logging
import secrets
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import aiohttp

from .const import (
    API_BASE,
    STATUS_API_BASE,
    AUTH_URL,
    CLIENT_ID,
    REDIRECT_URI,
    SCOPE,
    TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=30)
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 HomeAssistant-etoll_ro"
)


class EtollError(Exception):
    """Base error."""


class EtollAuthError(EtollError):
    """Wrong credentials or the account needs an action in the portal."""


class EtollConnectionError(EtollError):
    """Portal unreachable or answered unexpectedly."""


# --------------------------------------------------------------------------- #
# Login form parsing
# --------------------------------------------------------------------------- #
class _LoginFormParser(HTMLParser):
    """Find the Keycloak form that contains a password field."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None
        self.error_texts: list[str] = []
        self._capture_error = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "form":
            self._current = {
                "action": a.get("action", ""),
                "id": a.get("id", ""),
                "inputs": {},
                "has_password": False,
            }
            self.forms.append(self._current)
        elif tag == "input" and self._current is not None:
            name = a.get("name")
            if not name:
                return
            if a.get("type", "").lower() == "password":
                self._current["has_password"] = True
            self._current["inputs"][name] = a.get("value", "")
        # Keycloak error / feedback containers
        cls = a.get("class", "")
        ident = a.get("id", "")
        if ident in ("input-error", "kc-feedback-text") or "alert-error" in cls or "kc-feedback" in cls:
            self._capture_error += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._current = None
        if self._capture_error and tag in ("span", "div", "p"):
            self._capture_error -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_error and data.strip():
            self.error_texts.append(data.strip())


def parse_login_form(page: str) -> tuple[str, dict[str, str]] | None:
    """Return (action_url, hidden/default fields) of the password form."""
    parser = _LoginFormParser()
    parser.feed(page)
    for form in parser.forms:
        if form["has_password"] and form["action"]:
            return html.unescape(form["action"]), dict(form["inputs"])
    return None


def parse_login_error(page: str) -> str | None:
    """Return a Keycloak error message from a login page, if any."""
    parser = _LoginFormParser()
    parser.feed(page)
    return " ".join(parser.error_texts) or None


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class EtollApiClient:
    """Minimal client for the endpoints the integration needs."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._access_exp: float = 0
        self._refresh_token: str | None = None
        self._refresh_exp: float = 0
        self._lock = asyncio.Lock()

    # ---------------------------- authentication ---------------------------- #
    async def async_login(self) -> None:
        """Full username/password login (authorization code + PKCE)."""
        verifier, challenge = _pkce_pair()
        state = secrets.token_hex(16)
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "response_mode": "query",
            "kc_locale": "ro",
        }
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8"}

        # Separate cookie jar: Keycloak + F5 cookies must not leak into HA's
        # shared session.
        jar = aiohttp.CookieJar()
        try:
            async with aiohttp.ClientSession(
                cookie_jar=jar, timeout=_TIMEOUT, headers=headers
            ) as login_session:
                async with login_session.get(
                    f"{AUTH_URL}?{urlencode(params)}"
                ) as resp:
                    if resp.status != 200:
                        raise EtollConnectionError(
                            f"Login page returned HTTP {resp.status}"
                        )
                    page = await resp.text()
                    page_url = str(resp.url)

                form = parse_login_form(page)
                if form is None:
                    raise EtollConnectionError("Login form not found on sso.etoll.ro")
                action, fields = form
                action = urljoin(page_url, action)
                fields.update(
                    {
                        "username": self._username,
                        "password": self._password,
                        "loginMethod": fields.get("loginMethod") or "password",
                    }
                )
                fields.setdefault("login", "Autentificare")

                async with login_session.post(
                    action,
                    data=fields,
                    allow_redirects=False,
                    headers={"Referer": page_url, "Origin": "https://sso.etoll.ro"},
                ) as resp:
                    location = resp.headers.get("Location", "")
                    if resp.status in (301, 302, 303) and location.startswith(
                        REDIRECT_URI
                    ):
                        query = parse_qs(urlparse(location).query)
                    elif resp.status == 200:
                        body = await resp.text()
                        msg = parse_login_error(body)
                        if parse_login_form(body) is not None:
                            raise EtollAuthError(msg or "Invalid credentials")
                        # e.g. OTP, terms acceptance, password update
                        raise EtollAuthError(
                            msg
                            or "Account requires an action in the eToll portal "
                            "(OTP, terms, password update)"
                        )
                    else:
                        raise EtollConnectionError(
                            f"Unexpected login response HTTP {resp.status}"
                        )

                if query.get("state", [""])[0] != state:
                    raise EtollConnectionError("OAuth state mismatch")
                if "error" in query:
                    raise EtollAuthError(query.get("error_description", query["error"])[0])
                code = query.get("code", [None])[0]
                if not code:
                    raise EtollConnectionError("No authorization code received")

                await self._token_request(
                    {
                        "grant_type": "authorization_code",
                        "client_id": CLIENT_ID,
                        "code": code,
                        "redirect_uri": REDIRECT_URI,
                        "code_verifier": verifier,
                    },
                    session=login_session,
                )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise EtollConnectionError(f"Cannot reach sso.etoll.ro: {err}") from err

    async def _token_request(
        self, data: dict[str, str], session: aiohttp.ClientSession | None = None
    ) -> None:
        sess = session or self._session
        async with sess.post(
            TOKEN_URL,
            data=data,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            timeout=_TIMEOUT,
        ) as resp:
            payload = await resp.json(content_type=None)
            if resp.status == 400 and payload.get("error") == "invalid_grant":
                raise EtollAuthError(payload.get("error_description", "invalid_grant"))
            if resp.status != 200 or "access_token" not in payload:
                raise EtollConnectionError(
                    f"Token endpoint HTTP {resp.status}: {payload.get('error')}"
                )
        now = time.time()
        self._access_token = payload["access_token"]
        self._access_exp = now + int(payload.get("expires_in", 300)) - 60
        self._refresh_token = payload.get("refresh_token")
        self._refresh_exp = now + int(payload.get("refresh_expires_in", 1800)) - 60

    async def _ensure_token(self, force: bool = False) -> str:
        async with self._lock:
            now = time.time()
            if not force and self._access_token and now < self._access_exp:
                return self._access_token
            if self._refresh_token and now < self._refresh_exp:
                try:
                    await self._token_request(
                        {
                            "grant_type": "refresh_token",
                            "client_id": CLIENT_ID,
                            "refresh_token": self._refresh_token,
                        }
                    )
                    return self._access_token  # type: ignore[return-value]
                except EtollAuthError:
                    _LOGGER.debug("Refresh token rejected, logging in again")
                except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                    raise EtollConnectionError(str(err)) from err
            await self.async_login()
            return self._access_token  # type: ignore[return-value]

    # -------------------------------- requests ------------------------------ #
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{API_BASE}{path}"
        for attempt in (0, 1):
            token = await self._ensure_token(force=attempt == 1)
            try:
                async with self._session.get(
                    url,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                        "User-Agent": _USER_AGENT,
                    },
                    timeout=_TIMEOUT,
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        continue
                    if resp.status == 401:
                        raise EtollAuthError("API rejected the access token")
                    if resp.status >= 400:
                        raise EtollConnectionError(f"GET {path} -> HTTP {resp.status}")
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                raise EtollConnectionError(f"GET {path} failed: {err}") from err
        raise EtollConnectionError(f"GET {path} failed")

    async def _get_paged(self, path: str, key: str, params: dict[str, Any]) -> list[dict]:
        items: list[dict] = []
        cursor: str | None = None
        for _ in range(20):  # hard stop
            p = dict(params)
            if cursor:
                p["cursor"] = cursor
            data = await self._get(path, p)
            if isinstance(data, list):
                return items + data
            items.extend(data.get(key) or [])
            cursor = data.get("nextCursor")
            if not cursor:
                break
        return items

    async def async_get_profiles(self) -> list[dict]:
        data = await self._get("/profiles")
        return data if isinstance(data, list) else []

    async def async_get_vehicles(self) -> list[dict]:
        # computeVignetteEligibility adds vignetteEligibility.expirationDateCurrentVignette
        cars = await self._get_paged(
            "/vehicles",
            "vehicles",
            {"vehicleType": "CAR", "computeVignetteEligibility": "true", "size": 50},
        )
        everything = await self._get_paged("/vehicles", "vehicles", {"size": 50})
        by_id = {v["id"]: v for v in everything if v.get("id")}
        for car in cars:  # enriched version wins
            if car.get("id"):
                by_id[car["id"]] = car
        return list(by_id.values())

    async def async_get_active_tolls(self) -> list[dict]:
        return await self._get_paged(
            "/tolls", "tolls", {"status": "ACTIVE", "orderBy": "DSC", "size": 50}
        )

    async def async_get_notifications(self) -> list[dict]:
        data = await self._get("/notifications", {"status": "ACTIVE"})
        if isinstance(data, dict):
            data = data.get("notifications") or data.get("items") or []
        return [n for n in data if isinstance(n, dict)] if isinstance(data, list) else []

    async def async_get_status(self) -> dict[str, list[dict]]:
        """Public status page (Cachet) – no authentication needed."""
        out: dict[str, list[dict]] = {}
        for key, path, params in (
            ("components", "/components", {"per_page": 100}),
            ("incidents", "/incidents", {"per_page": 10, "sort": "-created_at"}),
            ("schedules", "/schedules", {"per_page": 10, "sort": "-created_at"}),
        ):
            try:
                async with self._session.get(
                    f"{STATUS_API_BASE}{path}",
                    params=params,
                    headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
                    timeout=_TIMEOUT,
                ) as resp:
                    if resp.status >= 400:
                        raise EtollConnectionError(f"status {path} -> HTTP {resp.status}")
                    payload = await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                raise EtollConnectionError(f"status {path} failed: {err}") from err
            out[key] = [
                item.get("attributes", {})
                for item in (payload or {}).get("data", [])
                if isinstance(item, dict)
            ]
        return out

    async def async_get_notification_count(self) -> int:
        data = await self._get("/notifications/summary")
        try:
            return int((data or {}).get("count", 0))
        except (TypeError, ValueError):
            return 0
