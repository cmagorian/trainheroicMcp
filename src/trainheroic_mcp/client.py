import json
import time
from pathlib import Path

import httpx

BASE_URL = "https://api.trainheroic.com"
TOKEN_CACHE_PATH = Path.home() / ".config" / "trainheroic" / "session.json"

# Confirmed login endpoint. The `t` query param is a millisecond timestamp used
# for cache-busting by the web client — we generate it fresh per request.
_LOGIN_URL = f"{BASE_URL}/auth"

_BASE_HEADERS = {
    "x-mobile-app-version": "8.25.0",
    "user-agent": "TrainHeroic/82515396 CFNetwork/3860.600.12 Darwin/25.5.0",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
}


class TrainHeroicClient:
    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        session_token: str | None = None,
    ):
        self._email = email
        self._password = password

        if session_token:
            self._token = session_token
        elif email and password:
            cached = self._load_cached_token()
            if cached:
                self._token = cached
            else:
                self._token = self._do_login()
                self._cache_token()
        else:
            raise ValueError("Provide either session_token or email+password")

        self._exercise_cache: list | None = None
        self._init_context()

    @property
    def _headers(self) -> dict:
        return {**_BASE_HEADERS, "session-token": self._token}

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _load_cached_token(self) -> str | None:
        if TOKEN_CACHE_PATH.exists():
            try:
                return json.loads(TOKEN_CACHE_PATH.read_text()).get("token")
            except Exception:
                return None
        return None

    def _cache_token(self) -> None:
        TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE_PATH.write_text(json.dumps({"token": self._token}))

    def _do_login(self) -> str:
        url = f"{_LOGIN_URL}?t={int(time.time() * 1000)}"
        resp = httpx.post(
            url,
            json={"email": self._email, "password": self._password},
            headers=_BASE_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get("session_id")
        if not token:
            raise RuntimeError(f"Login succeeded but response contained no session_id: {resp.text[:200]}")
        return token

    def _reauthenticate(self) -> None:
        if not (self._email and self._password):
            raise RuntimeError("Session token is expired and no credentials are configured for re-login")
        self._token = self._do_login()
        self._cache_token()

    # ── Context bootstrap ─────────────────────────────────────────────────────

    def _init_context(self) -> None:
        try:
            profile = self._get("/v5/user")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self._reauthenticate()
                profile = self._get("/v5/user")
            else:
                raise

        self.user_id: int = profile["id"]
        self.full_name: str = (
            f"{profile.get('nameFirst', '')} {profile.get('nameLast', '')}".strip()
        )

        licenses = self._get("/1.0/athlete/userlicense/")
        license_data = licenses.get("licenses", {})
        all_teams = (
            license_data.get("team", [])
            + license_data.get("team_share", [])
            + license_data.get("unlicensed", [])
        )
        self.team_id: int | None = all_teams[0]["id"] if all_teams else None
        self.program_id: int | None = all_teams[0].get("programId") if all_teams else None
        self.team_name: str = all_teams[0].get("title", self.full_name) if all_teams else self.full_name
        self._program_to_team: dict[int, int] = {
            t["programId"]: t["id"]
            for t in all_teams
            if t.get("programId") and t.get("id")
        }

    def team_id_for_program(self, program_id: int) -> int | None:
        """Return the team_id that owns the given program_id, or None if not found."""
        return self._program_to_team.get(program_id)

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        resp = httpx.get(
            f"{BASE_URL}{path}", headers=self._headers, params=params,
            timeout=30, follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict | None = None) -> dict | list:
        resp = httpx.post(
            f"{BASE_URL}{path}",
            headers={**self._headers, "content-type": "application/json"},
            json=body, timeout=30, follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, body: dict | None = None) -> dict | list:
        resp = httpx.put(
            f"{BASE_URL}{path}",
            headers={**self._headers, "content-type": "application/json"},
            json=body, timeout=30, follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> dict:
        resp = httpx.delete(
            f"{BASE_URL}{path}", headers=self._headers,
            timeout=30, follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def exercise_cache(self) -> list:
        if self._exercise_cache is None:
            self._exercise_cache = self._get(
                "/v5/users/exercises",
                params={"teamId": self.team_id, "userId": self.user_id},
            )
        return self._exercise_cache
