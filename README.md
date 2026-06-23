# TrainHeroic MCP Server

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**TrainHeroic MCP server — connect TrainHeroic to Claude via the Model Context Protocol.**

Give Claude (and other AI agents) direct access to your [TrainHeroic](https://trainheroic.com) workout data — history, exercise stats, personal records, and personal calendar — through the [Model Context Protocol](https://modelcontextprotocol.io).

Built from the TrainHeroic mobile API (iOS app v8.25.0, endpoints captured via mitmproxy).

---

## What you can do

Ask Claude things like:

- *"What workouts did I do this week?"*
- *"What's my working max for back squat and how has it changed?"*
- *"Show me my bench press PRs by rep count."*
- *"Log today's session — I did 4×5 back squat at 225 lbs, RPE 8."*
- *"Create a personal session for tomorrow and add deadlifts and Romanian deadlifts."*
- *"How did I feel after Monday's workout? What was my energy and stress survey?"*
- *"Who's on the leaderboard for Tuesday's workout?"*

---

## Quick Start

**Prerequisites:** [Python 3.12+](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
# 1. Clone and install
git clone https://github.com/cmagorian/trainheroicMcp
cd trainheroicMcp
make install

# 2. Add your credentials
cp .env.example .env
# Edit .env — see "Credentials" section below

# 3. Register with your AI client
make setup-claude      # Claude Code
make setup-openclaw    # OpenClaw
# See below for Claude Desktop and Cursor
```

Restart your AI client and ask: *"What did I train this week?"*

---

## Credentials

Copy `.env.example` to `.env` and choose one of two methods:

### Option A — Email + password (recommended)

```env
TRAINHEROIC_EMAIL=you@example.com
TRAINHEROIC_PASSWORD=yourpassword
```

The server logs in on first start and caches the session token to `~/.config/trainheroic/session.json`. Re-login is automatic when the token expires.

### Option B — Session token

If you'd rather not store your password:

1. Log in at [trainheroic.com](https://trainheroic.com)
2. Open DevTools (`F12`) → **Network** tab
3. Click any request to `api.trainheroic.com`
4. Under **Request Headers**, copy the `session-token` value

```env
TRAINHEROIC_SESSION_TOKEN=<your-session-token>
```

Verify your credentials before registering:

```bash
make check-env   # confirms .env is present and populated
make run         # starts the server — look for "Ready — logged in as ..." on stderr
```

---

## Registering with your AI client

### Claude Code

```bash
make setup-claude
```

This registers the server in `.claude/settings.json` for this project. Credentials are loaded from `.env` automatically.

Run `/mcp` in Claude Code (or restart) to pick up the new server.

### Claude Desktop

Open the config file for your OS:

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

### Cursor

Open **Cursor Settings** → **MCP** → **Add new MCP server**, or edit `~/.cursor/mcp.json` directly:

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

Restart Cursor after saving.

### OpenClaw

```bash
make setup-openclaw
```

This registers the server in `~/.openclaw/openclaw.json`. Restart OpenClaw to pick it up.

---

## Example prompts

### Checking history

```
What workouts did I complete last week?
Show me everything I trained in May.
Did I train on Monday?
```

### Exercise stats and PRs

```
What's my current working max for back squat?
Show me my bench press PRs broken down by rep count.
What were my last 3 performances on Romanian deadlifts?
```

### Logging a session

```
Create a personal session for today and add back squat, bench press, and cable rows.
Log my workout — I completed all sets. RPE was 7, rating 8 out of 10.
```

### Surveys and recovery

```
What were my energy and stress scores after Tuesday's workout?
Submit my readiness survey: sleep was good, mood was great, energy was ok.
```

### Social

```
Who's on the leaderboard for this week's main lift?
What comments are on today's workout?
```

---

## Available tools

### Core data

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_user_profile` | Name, ID, coach status | — |
| `get_team_info` | Teams, program IDs, coaches | — |
| `get_workout_history` | Workouts in a date range (flat summary by default) | `start_date`, `end_date`, `weeks_back`, `include_sets` |
| `get_workout_details` | Full sets + logged weights for one session | `program_workout_id`, `program_id` |
| `get_exercise_stats` | Last performance, PR, working max | `exercise_id`, `stat_date` |
| `get_personal_records` | All PRs by rep count | `exercise_id` |
| `get_working_max` | Current working max | `exercise_id` |

> **Tip:** `get_workout_history` returns compact summaries (date, title, rating, RPE, notes) by default. Pass `include_sets=True` for set-level data on a 1–3 day window, or call `get_workout_details` for a single session.

### Exercise library

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_exercise_library` | Full library; filter by name | `query` (optional substring) |
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
| `get_workout_surveys` | Sleep/mood/energy/soreness/stress data | `saved_workout_ids` |
| `submit_survey` | Answer a survey question | `saved_workout_id`, `question_id`, `answer_id` |
| `get_workout_messages` | Comments on a workout | `program_workout_id` |
| `get_workout_leaderboard` | Full leaderboard for a workout | `program_workout_id` |

**Survey reference:**

| | Sleep | Mood | Energy | Soreness | Stress |
|-|-------|------|--------|----------|--------|
| `question_id` | 8 | 9 | 10 | 11 | 12 |

| `answer_id` | 1 | 2 | 3 | 4 | 5 |
|-------------|---|---|---|---|---|
| Meaning | Awful | Poor | Ok | Good | Excellent |

---

## Deploying online (access from any machine)

Host the server on [Railway](https://railway.app) so any device running Claude Code, Claude Desktop, or OpenClaw can connect to it over HTTPS — no local Python install needed on the client.

### Step 1 — Generate an auth token

```bash
make generate-token
# prints: MCP_AUTH_TOKEN=e5b7a8e3...
```

Copy the full line — you'll need it in Steps 2 and 3.

### Step 2 — Deploy to Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Select the repository — Railway auto-detects the `Dockerfile`
4. In **Variables**, add:

| Variable | Value |
|----------|-------|
| `MCP_TRANSPORT` | `http` |
| `TRAINHEROIC_EMAIL` | your email |
| `TRAINHEROIC_PASSWORD` | your password |
| `MCP_AUTH_TOKEN` | the token from Step 1 |

5. Click **Deploy**. Railway assigns a URL like `https://trainheroicmcp-production.up.railway.app`

Check the deploy logs for:
```
INFO [trainheroic-mcp] Ready — logged in as Your Name (team: Your Team)
INFO [trainheroic-mcp] HTTP transport — listening on 0.0.0.0:8000/mcp
```

### Step 3 — Connect from any machine

Replace `YOUR_URL` with your Railway URL and `YOUR_TOKEN` with the token from Step 1.

**Claude Code:**
```bash
claude mcp add \
  --transport http \
  --header "Authorization: Bearer YOUR_TOKEN" \
  trainheroic \
  https://YOUR_URL/mcp
```

**Claude Desktop / Cursor** (`claude_desktop_config.json` or `~/.cursor/mcp.json`):
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

**OpenClaw:**
```bash
openclaw mcp set trainheroic \
  '{"type":"http","url":"https://YOUR_URL/mcp","headers":{"Authorization":"Bearer YOUR_TOKEN"}}'
```

**Test the connection:**
```bash
curl -s \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  https://YOUR_URL/mcp
# Should return an MCP protocol response, not 401
```

**Run HTTP transport locally (before deploying):**
```bash
MCP_AUTH_TOKEN=test-token make run-http
# Server starts on http://localhost:8000/mcp
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `No TrainHeroic credentials found` | `.env` missing or empty | `cp .env.example .env` and add credentials |
| `401 Unauthorized` on startup | Expired or invalid token | Delete `~/.config/trainheroic/session.json` and restart; the server re-logs in |
| `401` from `get_workout_details` | Wrong team resolved | Pass `program_id` from the `get_workout_history` item alongside `program_workout_id` |
| Server starts but Claude can't find it | Not registered or client not restarted | Re-run `make setup-claude` and restart Claude |
| Responses seem incomplete | Date range too wide | Use 1–2 week windows; call `get_workout_details` per session for set data |

---

## Known limitations

| Feature | Reason unavailable |
|---------|-------------------|
| Lift goals | Requires Athlete Pro subscription |
| Nutrition calendar | Requires Athlete Pro subscription |
| Program listing | Coach accounts only |
| Data export | Backend returns 504 timeout |

---

## Development

### Running tests

No credentials needed — all HTTP is intercepted by `pytest-httpx`.

```bash
make test                                  # quiet summary
make test-v                                # verbose, one line per test
uv run pytest -k "TestLogin"              # single class
uv run pytest tests/test_client.py        # single file
```

### Project structure

```
src/trainheroic_mcp/
├── client.py     # TrainHeroicClient — auth, token cache, HTTP helpers
└── server.py     # FastMCP server — 19 tool definitions, response projectors

tests/
├── conftest.py      # fixtures: cache isolation (autouse), th_client, patched_server
├── helpers.py       # shared constants + add_init_responses helper
├── test_client.py   # init, login, token cache, HTTP helpers
└── test_tools.py    # one test class per tool
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
