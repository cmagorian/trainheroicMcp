# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install       # uv sync --all-groups (runtime + dev deps)
make test          # run full test suite (no credentials needed)
make test-v        # verbose test output
make run           # start MCP server (stdio transport, requires .env)
make run-http      # start MCP server (HTTP on :8000, requires MCP_AUTH_TOKEN)
make check-env     # verify .env has credentials

# Run a single test file or class
uv run pytest tests/test_client.py
uv run pytest -k "TestLogin"
```

## Architecture

Two source files, no framework beyond `FastMCP` and `httpx`:

**`src/trainheroic_mcp/client.py` — `TrainHeroicClient`**
- Handles auth: email+password → POST `/auth?t=<ms_timestamp>` → `session_id` token; or accepts a direct session token
- Token cached to `~/.config/trainheroic/session.json`. On 401 during `_init_context`, re-logs in and recaches
- `_init_context()` runs at construction time: fetches `/v5/user` (sets `user_id`, `full_name`) and `/1.0/athlete/userlicense/` (sets `team_id`, `program_id`, `team_name`)
- HTTP helpers: `_get`, `_post`, `_put`, `_delete` — all synchronous `httpx` calls; raise on non-2xx
- Do NOT include `Api-Token`, `Origin`, or `Referer` headers — these break the mobile API

**`src/trainheroic_mcp/server.py` — FastMCP server**
- Module-level `_client: TrainHeroicClient | None = None`; `_get_client()` lazily creates it from env vars
- 19 tools registered with `@mcp.tool()`, grouped by priority in comments
- `lifespan` context manager logs startup/auth status to stderr
- Transport: `stdio` by default; set `MCP_TRANSPORT=http` for HTTP (uses `uvicorn`)
- `MCP_AUTH_TOKEN` enables bearer-token auth for HTTP transport via `StaticTokenVerifier`

## Adding a new tool

1. Add `@mcp.tool()` function to `server.py` — call `_get_client()` and use `_get`/`_post`/`_put`/`_delete`
2. Add a test class to `tests/test_tools.py` using `patched_server` and `httpx_mock` fixtures

```python
# server.py
@mcp.tool()
def get_something(param: int) -> dict:
    """Docstring becomes the tool description shown to the AI."""
    return _get_client()._get(f"/v5/something/{param}")
```

```python
# tests/test_tools.py
class TestGetSomething:
    def test_calls_correct_endpoint(self, patched_server, httpx_mock):
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/something/1", json={"ok": True})
        result = server.get_something(1)
        assert result["ok"] is True
```

## Test patterns

- `isolated_token_cache` fixture is `autouse=True` — redirects token cache to a tmp dir for every test
- `th_client` fixture: `TrainHeroicClient(session_token="test-token")` with init calls pre-mocked via `add_init_responses(httpx_mock)`
- `patched_server` fixture: sets `server._client` to the mocked client so tool functions bypass auth
- `tests/helpers.py` has shared constants (`BASE`, `MOCK_PROFILE`, `MOCK_LICENSE`) and `add_init_responses()`
- All HTTP is intercepted by `pytest-httpx` — no real network calls in tests

## Credentials

Copy `.env.example` to `.env`. Session token is the preferred auth method (email+password login also works via POST `/auth`). Token is cached after first login; delete `~/.config/trainheroic/session.json` to force re-login.

## Known broken endpoints

`/v5/users/goals/lifts` and `/v5/calendars/athletes/{id}/nutrition` require Athlete Pro (401). `/v5/programs` requires a coach account (401). `/v5/users/dataExport` times out (504).
