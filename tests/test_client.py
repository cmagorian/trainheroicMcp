import json

import httpx
import pytest

from trainheroic_mcp.client import (
    BASE_URL,
    TOKEN_CACHE_PATH,
    TrainHeroicClient,
    _LOGIN_URL,
)
from tests.helpers import BASE, MOCK_LICENSE, MOCK_PROFILE, add_init_responses


# ── Initialisation ─────────────────────────────────────────────────────────────

class TestInit:
    def test_session_token_accepted(self, httpx_mock):
        add_init_responses(httpx_mock)
        c = TrainHeroicClient(session_token="my-token")
        assert c._token == "my-token"

    def test_no_credentials_raises(self):
        with pytest.raises(ValueError, match="Provide either"):
            TrainHeroicClient()

    def test_user_id_populated(self, httpx_mock):
        add_init_responses(httpx_mock)
        c = TrainHeroicClient(session_token="tok")
        assert c.user_id == 42

    def test_full_name_populated(self, httpx_mock):
        add_init_responses(httpx_mock)
        c = TrainHeroicClient(session_token="tok")
        assert c.full_name == "Chris Magorian"

    def test_team_id_populated(self, httpx_mock):
        add_init_responses(httpx_mock)
        c = TrainHeroicClient(session_token="tok")
        assert c.team_id == 1001

    def test_program_id_populated(self, httpx_mock):
        add_init_responses(httpx_mock)
        c = TrainHeroicClient(session_token="tok")
        assert c.program_id == 2001

    def test_team_name_populated(self, httpx_mock):
        add_init_responses(httpx_mock)
        c = TrainHeroicClient(session_token="tok")
        assert c.team_name == "Team Alpha"

    def test_no_team_falls_back_to_full_name(self, httpx_mock):
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", json=MOCK_PROFILE)
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE}/1.0/athlete/userlicense/",
            json={"licenses": {"team": [], "team_share": [], "unlicensed": []}},
        )
        c = TrainHeroicClient(session_token="tok")
        assert c.team_id is None
        assert c.program_id is None
        assert c.team_name == "Chris Magorian"

    def test_team_share_counts_as_team(self, httpx_mock):
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", json=MOCK_PROFILE)
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE}/1.0/athlete/userlicense/",
            json={
                "licenses": {
                    "team": [],
                    "team_share": [{"id": 999, "programId": 888, "title": "Shared Team"}],
                    "unlicensed": [],
                }
            },
        )
        c = TrainHeroicClient(session_token="tok")
        assert c.team_id == 999
        assert c.team_name == "Shared Team"

    def test_session_token_sent_in_header(self, httpx_mock):
        add_init_responses(httpx_mock)
        TrainHeroicClient(session_token="secret-tok")
        req = httpx_mock.get_requests()[0]
        assert req.headers["session-token"] == "secret-tok"

    def test_mobile_app_version_header_sent(self, httpx_mock):
        add_init_responses(httpx_mock)
        TrainHeroicClient(session_token="tok")
        req = httpx_mock.get_requests()[0]
        assert req.headers["x-mobile-app-version"] == "8.25.0"


# ── Login / authentication ─────────────────────────────────────────────────────

def _mock_login(httpx_mock, token: str = "test-tok") -> None:
    """Add a successful login response. URL uses regex to match the dynamic ?t= timestamp."""
    import re
    httpx_mock.add_response(
        method="POST",
        url=re.compile(rf"{re.escape(_LOGIN_URL)}\?t=\d+"),
        json={"id": 42, "scope": "athlete", "role": "athlete", "session_id": token},
    )


class TestLogin:
    def test_email_password_calls_auth_endpoint(self, httpx_mock):
        _mock_login(httpx_mock, "tok-1")
        add_init_responses(httpx_mock)
        c = TrainHeroicClient(email="u@e.com", password="pass")
        assert c._token == "tok-1"

    def test_login_request_includes_timestamp_param(self, httpx_mock):
        _mock_login(httpx_mock)
        add_init_responses(httpx_mock)
        TrainHeroicClient(email="u@e.com", password="pass")
        req = [r for r in httpx_mock.get_requests() if r.method == "POST"][0]
        assert "t" in req.url.params
        assert req.url.params["t"].isdigit()

    def test_login_sends_email_and_password_in_body(self, httpx_mock):
        _mock_login(httpx_mock)
        add_init_responses(httpx_mock)
        TrainHeroicClient(email="user@example.com", password="secret")
        import json as _json
        req = [r for r in httpx_mock.get_requests() if r.method == "POST"][0]
        body = _json.loads(req.content)
        assert body == {"email": "user@example.com", "password": "secret"}

    def test_login_raises_on_http_error(self, httpx_mock):
        import re
        httpx_mock.add_response(
            method="POST",
            url=re.compile(rf"{re.escape(_LOGIN_URL)}\?t=\d+"),
            status_code=401,
        )
        with pytest.raises(httpx.HTTPStatusError):
            TrainHeroicClient(email="u@e.com", password="pass")

    def test_login_raises_when_session_id_missing(self, httpx_mock):
        import re
        httpx_mock.add_response(
            method="POST",
            url=re.compile(rf"{re.escape(_LOGIN_URL)}\?t=\d+"),
            json={"id": 42},  # no session_id field
        )
        with pytest.raises(RuntimeError, match="no session_id"):
            TrainHeroicClient(email="u@e.com", password="pass")

    def test_reauth_on_401_during_init(self, httpx_mock):
        import re
        login_pattern = re.compile(rf"{re.escape(_LOGIN_URL)}\?t=\d+")
        httpx_mock.add_response(method="POST", url=login_pattern, json={"session_id": "initial-tok"})
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", status_code=401)
        httpx_mock.add_response(method="POST", url=login_pattern, json={"session_id": "fresh-tok"})
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", json=MOCK_PROFILE)
        httpx_mock.add_response(method="GET", url=f"{BASE}/1.0/athlete/userlicense/", json=MOCK_LICENSE)
        c = TrainHeroicClient(email="u@e.com", password="pass")
        assert c._token == "fresh-tok"
        assert c.user_id == 42

    def test_session_token_skips_login(self, httpx_mock):
        add_init_responses(httpx_mock)
        TrainHeroicClient(session_token="direct-tok")
        post_reqs = [r for r in httpx_mock.get_requests() if r.method == "POST"]
        assert post_reqs == []

    def test_session_token_raises_on_401(self, httpx_mock):
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", status_code=401)
        with pytest.raises(RuntimeError, match="expired"):
            TrainHeroicClient(session_token="bad-token")


# ── Token cache ────────────────────────────────────────────────────────────────

class TestTokenCache:
    def test_cached_token_used_instead_of_login(self, httpx_mock, tmp_path, monkeypatch):
        cache_file = tmp_path / "session.json"
        cache_file.write_text(json.dumps({"token": "cached-tok"}))
        monkeypatch.setattr("trainheroic_mcp.client.TOKEN_CACHE_PATH", cache_file)
        add_init_responses(httpx_mock)
        c = TrainHeroicClient(email="u@e.com", password="pass")
        post_reqs = [r for r in httpx_mock.get_requests() if r.method == "POST"]
        assert post_reqs == []
        assert c._token == "cached-tok"

    def test_token_written_to_cache_after_login(self, httpx_mock, tmp_path, monkeypatch):
        cache_file = tmp_path / "session.json"
        monkeypatch.setattr("trainheroic_mcp.client.TOKEN_CACHE_PATH", cache_file)
        _mock_login(httpx_mock, "brand-new")
        add_init_responses(httpx_mock)
        TrainHeroicClient(email="u@e.com", password="pass")
        assert json.loads(cache_file.read_text())["token"] == "brand-new"

    def test_new_token_cached_after_reauth(self, httpx_mock, tmp_path, monkeypatch):
        import re
        cache_file = tmp_path / "session.json"
        monkeypatch.setattr("trainheroic_mcp.client.TOKEN_CACHE_PATH", cache_file)
        login_pattern = re.compile(rf"{re.escape(_LOGIN_URL)}\?t=\d+")
        httpx_mock.add_response(method="POST", url=login_pattern, json={"session_id": "initial-tok"})
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", status_code=401)
        httpx_mock.add_response(method="POST", url=login_pattern, json={"session_id": "re-authed"})
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", json=MOCK_PROFILE)
        httpx_mock.add_response(method="GET", url=f"{BASE}/1.0/athlete/userlicense/", json=MOCK_LICENSE)
        TrainHeroicClient(email="u@e.com", password="pass")
        assert json.loads(cache_file.read_text())["token"] == "re-authed"

    def test_corrupt_cache_file_falls_back_to_login(self, httpx_mock, tmp_path, monkeypatch):
        cache_file = tmp_path / "session.json"
        cache_file.write_text("not json {{")
        monkeypatch.setattr("trainheroic_mcp.client.TOKEN_CACHE_PATH", cache_file)
        _mock_login(httpx_mock, "fresh")
        add_init_responses(httpx_mock)
        c = TrainHeroicClient(email="u@e.com", password="pass")
        assert c._token == "fresh"


# ── HTTP helpers ───────────────────────────────────────────────────────────────

class TestHTTPHelpers:
    def test_get_sends_session_token_header(self, httpx_mock, th_client):
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", json={"ok": True})
        th_client._get("/v5/user")
        req = httpx_mock.get_requests()[-1]
        assert req.headers["session-token"] == "test-token"

    def test_post_sends_content_type(self, httpx_mock, th_client):
        httpx_mock.add_response(
            method="POST", url=f"{BASE}/v5/programWorkouts/personal", json={"id": 1}
        )
        th_client._post("/v5/programWorkouts/personal", {"date": "2026-06-01"})
        req = httpx_mock.get_requests()[-1]
        assert req.headers["content-type"] == "application/json"

    def test_put_sends_content_type(self, httpx_mock, th_client):
        httpx_mock.add_response(
            method="PUT",
            url=f"{BASE}/v5/personalCalendar/workouts/9/addExercises",
            json=[],
        )
        th_client._put("/v5/personalCalendar/workouts/9/addExercises", {})
        req = httpx_mock.get_requests()[-1]
        assert req.headers["content-type"] == "application/json"

    def test_delete_returns_empty_dict_on_no_content(self, httpx_mock, th_client):
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE}/v5/programWorkouts/5",
            status_code=204,
            content=b"",
        )
        result = th_client._delete("/v5/programWorkouts/5")
        assert result == {}

    def test_delete_returns_json_when_body_present(self, httpx_mock, th_client):
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE}/v5/programWorkouts/5",
            json={"deleted": True},
        )
        result = th_client._delete("/v5/programWorkouts/5")
        assert result == {"deleted": True}

    def test_get_raises_on_http_error(self, httpx_mock, th_client):
        httpx_mock.add_response(
            method="GET", url=f"{BASE}/v5/user", status_code=500
        )
        with pytest.raises(httpx.HTTPStatusError):
            th_client._get("/v5/user")


# ── Exercise cache ─────────────────────────────────────────────────────────────

class TestExerciseCache:
    def test_cache_initially_none(self, th_client):
        assert th_client._exercise_cache is None

    def test_cache_populated_on_first_call(self, httpx_mock, th_client):
        import re
        exercises = [{"id": 100, "title": "Squat"}]
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/users/exercises"),
            json=exercises,
        )
        result = th_client.exercise_cache()
        assert result == exercises
        assert th_client._exercise_cache == exercises

    def test_cache_not_refetched_on_second_call(self, httpx_mock, th_client):
        import re
        exercises = [{"id": 100, "title": "Squat"}]
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/users/exercises"),
            json=exercises,
        )
        th_client.exercise_cache()
        th_client.exercise_cache()  # second call — no second HTTP request
        # If a second request were made, pytest-httpx would raise (no second mock registered)
        assert th_client._exercise_cache == exercises
