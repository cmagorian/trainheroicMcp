# TrainHeroic MCP Server

An MCP server that gives Claude (and other AI agents) direct access to your
[TrainHeroic](https://trainheroic.com) workout data, exercise library, and personal calendar.

Built from the mobile API (iOS app v8.25.0, endpoints captured via mitmproxy).

---

## Prerequisites

| Requirement | Install |
|-------------|---------|
| Python 3.12+ | [python.org](https://www.python.org/downloads/) |
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Claude Code or OpenClaw | see below |

---

## Setup

### 1. Install dependencies

```bash
git clone <repo-url> trainheroicMcp
cd trainheroicMcp
make install
```

### 2. Configure credentials

```bash
cp .env.example .env
# edit .env and fill in your credentials
```

**Option A — email + password** *(recommended)*

```env
TRAINHEROIC_EMAIL=you@example.com
TRAINHEROIC_PASSWORD=yourpassword
```

The server authenticates on first start and caches the session token to
`~/.config/trainheroic/session.json`. Subsequent starts reuse the cached token
and only re-login if it expires.

**Option B — session token directly**

1. Log in at [trainheroic.com](https://trainheroic.com)
2. Open DevTools (`F12`) → **Network** tab
3. Click any request to `api.trainheroic.com`
4. Under **Request Headers**, find `session-token`
5. Copy that value into `.env`:

```env
TRAINHEROIC_SESSION_TOKEN=<your-session-token>
```

### 3. Verify credentials

```bash
make check-env   # confirms .env exists and has credentials
make run         # starts the server; look for "Ready — logged in as ..." on stderr
```

Press `Ctrl+C` to stop. The server waits silently for MCP protocol input — that's
normal for stdio transport.

---

## Register with your AI client

### Claude Code

```bash
make setup-claude
```

This runs:
```bash
claude mcp add --scope project trainheroic -- uv run --directory "$PWD" python -m trainheroic_mcp.server
```

The server is registered in `.claude/settings.json` for this project. Credentials
are loaded from the `.env` file in the repo root automatically.

Restart Claude Code (or run `/mcp` to reload servers without restarting).

### OpenClaw

```bash
make setup-openclaw
```

This runs:
```bash
openclaw mcp set trainheroic '{"command":"uv","args":["run","python","-m","trainheroic_mcp.server"],"cwd":"<repo path>"}'
```

The server is registered in `~/.openclaw/openclaw.json`. Restart OpenClaw to
pick up the change. Because `cwd` is set to the repo root, the `.env` file is
found automatically at startup.

### Claude Desktop (manual)

Open your Claude Desktop config:

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

Add the `trainheroic` entry — replace the path and credentials:

```json
{
  "mcpServers": {
    "trainheroic": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/absolute/path/to/trainheroicMcp",
        "python", "-m", "trainheroic_mcp.server"
      ],
      "env": {
        "TRAINHEROIC_EMAIL": "you@example.com",
        "TRAINHEROIC_PASSWORD": "yourpassword"
      }
    }
  }
}
```

Restart Claude Desktop after saving.

---

## Confirming it works

Once registered, ask Claude:

> *"What workouts did I do this week?"*
> *"What's my working max for back squat?"*
> *"Show me my recent exercise history."*

If something is wrong, the tools return a clear error message explaining what's
missing (e.g. missing credentials, expired token).

---

## Deploying online (use from any machine)

Deploy to [Railway](https://railway.app) to host the server in the cloud. Once
deployed, any machine running Claude Code or OpenClaw can connect to it over
HTTPS — no local Python install required on the client side.

### Step 1 — Generate an auth token

The deployed server is public by default. Protect it with a pre-shared bearer token:

```bash
make generate-token
# prints: MCP_AUTH_TOKEN=e5b7a8e39538541...
```

Copy the full line — you'll need it in Steps 2 and 3.

### Step 2 — Deploy to Railway

1. Push this repo to GitHub (it must be a git repo)
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Select this repository — Railway auto-detects the `Dockerfile`
4. In **Variables**, add all of these:

| Variable | Value |
|----------|-------|
| `MCP_TRANSPORT` | `http` |
| `TRAINHEROIC_EMAIL` | your email |
| `TRAINHEROIC_PASSWORD` | your password |
| `MCP_AUTH_TOKEN` | the token from Step 1 |

5. Click **Deploy**. Railway assigns a public URL like `https://trainheroicmcp-production.up.railway.app`

Check the deploy logs — you should see:
```
INFO [trainheroic-mcp] Ready — logged in as Your Name (team: Team Name)
INFO [trainheroic-mcp] HTTP transport — listening on 0.0.0.0:8000/mcp
```

### Step 3 — Connect from any machine

Replace `YOUR_URL` with the Railway URL and `YOUR_TOKEN` with the token from Step 1.

**Claude Code:**
```bash
claude mcp add \
  --transport http \
  --header "Authorization: Bearer YOUR_TOKEN" \
  trainheroic \
  https://YOUR_URL/mcp
```

**OpenClaw:**
```bash
openclaw mcp set trainheroic \
  '{"type":"http","url":"https://YOUR_URL/mcp","headers":{"Authorization":"Bearer YOUR_TOKEN"}}'
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "trainheroic": {
      "type": "http",
      "url": "https://YOUR_URL/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

### Testing the deployed server

```bash
curl -s \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  https://YOUR_URL/mcp
# Should return an MCP protocol response (not 401)
```

### Running HTTP transport locally (for testing before deploy)

```bash
MCP_AUTH_TOKEN=test-token make run-http
# Server starts on http://localhost:8000/mcp
```

---

## Available tools

### Core data

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_user_profile` | Name, ID, coach status | — |
| `get_team_info` | Teams, program IDs, coaches | — |
| `get_workout_history` | Workouts in a date range | `start_date`, `end_date`, `weeks_back` |
| `get_workout_details` | Full sets + logged weights for one session | `program_workout_id` |
| `get_exercise_stats` | Last performance, PR, working max | `exercise_id`, `stat_date` |
| `get_personal_records` | All PRs by rep count | `exercise_id` |
| `get_working_max` | Current working max | `exercise_id` |

### Exercise library

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_exercise_library` | Full library; filter by name | `query` (optional substring filter) |
| `get_circuit_library` | Full circuit library | — |
| `get_recent_exercises` | Recently used exercises | — |
| `get_recent_circuits` | Recently used circuits | — |

### Personal calendar

| Tool | What it does | Key params |
|------|-------------|------------|
| `create_personal_session` | Create a new session | `session_date` (YYYY-MM-DD) |
| `add_exercises_to_session` | Add exercises in order | `workout_id`, `exercise_ids` |
| `log_workout` | Save a completed workout | `saved_workout_id`, `workout_id`, `date_string`, `blocks`, `notes`, `rpe`, `workout_rating` |
| `delete_session` | Delete a session | `program_workout_id` |

### Surveys & messaging

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_workout_surveys` | Sleep/mood/energy/soreness/stress survey | `saved_workout_ids` |
| `submit_survey` | Answer a survey question | `saved_workout_id`, `question_id`, `answer_id` |
| `get_workout_messages` | Comments on a workout | `program_workout_id` |
| `get_workout_leaderboard` | Full leaderboard for a workout | `program_workout_id` |

**Survey reference:**

| | Sleep | Mood | Energy | Soreness | Stress |
|-|-------|------|--------|----------|--------|
| question_id | 8 | 9 | 10 | 11 | 12 |

| answer_id | 1 | 2 | 3 | 4 | 5 |
|-----------|---|---|---|---|---|
| meaning | Awful | Poor | Ok | Good | Excellent |

---

## Known limitations

These endpoints are gated or broken on the backend:

| Tool | Reason |
|------|--------|
| Lift goals | Requires Athlete Pro subscription |
| Nutrition calendar | Requires Athlete Pro subscription |
| Program listing | Coach accounts only |
| Data export | Backend returns 504 timeout |

---

## Development

### Running tests

No credentials needed — all HTTP calls are intercepted by `pytest-httpx`.

```bash
make test              # quiet summary
make test-v            # verbose, one line per test
uv run pytest -k "TestLogin"           # one class
uv run pytest tests/test_client.py    # one file
```

### Project structure

```
src/trainheroic_mcp/
├── client.py     # TrainHeroicClient — auth, token cache, HTTP helpers
└── server.py     # FastMCP server — 19 tool definitions + startup logging

tests/
├── conftest.py   # fixtures: cache isolation (autouse), th_client, patched_server
├── helpers.py    # shared constants + add_init_responses helper
├── test_client.py   # 33 tests: init, login, token cache, HTTP helpers
└── test_tools.py    # 33 tests: one class per tool
```

### Adding a new tool

1. Add the function to `server.py` with `@mcp.tool()`.
2. Add a test class to `tests/test_tools.py` using the `patched_server` fixture.

```python
# server.py
@mcp.tool()
def get_athlete_pro_status() -> dict:
    """Check whether the user has an active Athlete Pro subscription."""
    return _get_client()._get("/v5/athletePro/access")
```

```python
# tests/test_tools.py
class TestGetAthleteProStatus:
    def test_calls_correct_endpoint(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE}/v5/athletePro/access",
            json={"hasAthleteProAccess": False},
        )
        result = server.get_athlete_pro_status()
        assert result["hasAthleteProAccess"] is False
```
