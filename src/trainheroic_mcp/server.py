import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import date, timedelta

from dotenv import load_dotenv
from mcp.server.auth.provider import AccessToken
from mcp.server.fastmcp import FastMCP

from trainheroic_mcp.client import TrainHeroicClient

load_dotenv()

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s [trainheroic-mcp] %(message)s",
)
log = logging.getLogger(__name__)


class StaticTokenVerifier:
    """Accepts a single pre-shared bearer token set via MCP_AUTH_TOKEN."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if token == self._token:
            return AccessToken(token=token, client_id="trainheroic-mcp", scopes=[])
        return None


@asynccontextmanager
async def lifespan(server):
    log.info("Starting — authenticating with TrainHeroic...")
    try:
        client = _get_client()
        log.info(f"Ready — logged in as {client.full_name} (team: {client.team_name})")
    except RuntimeError as e:
        log.error(str(e))
        log.error("All tools will return errors until credentials are configured.")
    except Exception as e:
        log.error(f"Unexpected startup error: {e}")
    yield
    log.info("Stopped")


_auth_token = os.getenv("MCP_AUTH_TOKEN")
mcp = FastMCP(
    "TrainHeroic",
    lifespan=lifespan,
    token_verifier=StaticTokenVerifier(_auth_token) if _auth_token else None,
    instructions="""
You are connected to the TrainHeroic MCP server, which wraps the TrainHeroic mobile API.

## Avoiding oversized responses (important)
API responses can be large. Follow this two-step pattern to avoid truncation:

**Step 1 — scan with get_workout_history (no sets)**
get_workout_history returns lightweight metadata by default (include_sets=False):
date, workout title, rating, RPE, session notes, and the IDs you need for follow-up calls.
Use this to find sessions, read top-level notes, and identify what the user did on which days.
Keep date ranges narrow — 1–2 weeks at a time. For longer histories, make multiple calls.

**Step 2 — drill in with get_workout_details**
Once you know the specific session(s) the user cares about, call
get_workout_details(program_workout_id=..., program_id=...) to get the full set-level data
(exercises, weights, reps, set notes) for that one session.
Always pass program_id (from the get_workout_history item) so the server resolves the
correct team automatically — omitting it can cause 401 errors on multi-team accounts.

Only use get_workout_history with include_sets=True if you need set data for multiple
days at once AND the range is 1–3 days.

## Workflow for logging a workout
1. get_workout_history → find the session (grab program_workout_id and program_id)
2. get_workout_details(program_workout_id, program_id=...) → get saved_workout_id and block IDs
3. log_workout(saved_workout_id, workout_id, date_string, blocks=[...])
""",
)

_client: TrainHeroicClient | None = None


def _get_client() -> TrainHeroicClient:
    global _client
    if _client is None:
        token = os.getenv("TRAINHEROIC_SESSION_TOKEN")
        email = os.getenv("TRAINHEROIC_EMAIL")
        password = os.getenv("TRAINHEROIC_PASSWORD")
        if not token and not (email and password):
            raise RuntimeError(
                "No TrainHeroic credentials found. "
                "Set TRAINHEROIC_EMAIL + TRAINHEROIC_PASSWORD or TRAINHEROIC_SESSION_TOKEN "
                "in your .env file or the MCP server 'env' config block."
            )
        _client = TrainHeroicClient(
            email=email or None,
            password=password or None,
            session_token=token or None,
        )
    return _client


# ── Helpers ───────────────────────────────────────────────────────────────────

# Fields that are never useful to a model: video/image URLs and related flags.
_MEDIA_KEYS = frozenset({
    "videoUrl", "thumbnailUrl", "videoThumbnailUrl",
    "imageUrl", "profileImage", "hasVideo",
})


def _trim_response(obj):
    """Recursively strip media/URL fields from any API response."""
    if isinstance(obj, dict):
        return {k: _trim_response(v) for k, v in obj.items() if k not in _MEDIA_KEYS}
    if isinstance(obj, list):
        return [_trim_response(i) for i in obj]
    return obj


def _project_history_item(w: dict) -> dict:
    """
    Flatten a workout-range item to the minimum fields needed for scanning history.
    Drops all nested metadata — use get_workout_details for set-level data.
    """
    ssw = w.get("summarizedSavedWorkout") or {}
    sw = ssw.get("saved_workout") or {}
    return {
        "id": w.get("id"),
        "workout_id": w.get("workout_id"),
        "program_id": w.get("program_id"),
        "date": w.get("date"),
        "workout_title": w.get("workout_title"),
        "feed_item_id": w.get("feed_item_id"),
        "saved_workout_id": sw.get("id"),
        "completed": sw.get("completed"),
        "workout_rating": sw.get("workout_rating"),
        "rpe": sw.get("rpe"),
        "notes": sw.get("notes"),
    }


# ── Priority 1: Core data ──────────────────────────────────────────────────────

@mcp.tool()
def get_user_profile() -> dict:
    """Get the current user's profile (name, ID, coach status, etc.)."""
    return _get_client()._get("/v5/user")


@mcp.tool()
def get_team_info() -> dict:
    """Get the athlete's team memberships and license info (team IDs, program IDs, coaches)."""
    return _get_client()._get("/1.0/athlete/userlicense/")


@mcp.tool()
def get_workout_history(
    start_date: str | None = None,
    end_date: str | None = None,
    weeks_back: int = 4,
    include_sets: bool = False,
) -> list:
    """
    Get workout history for a date range.

    Dates must be YYYY-MM-DD. If omitted, defaults to the last `weeks_back` weeks.
    Fetches one day at a time to guarantee the full day's data is returned.

    By default (include_sets=False) each item is projected to a flat summary:
    id, workout_id, program_id, date, workout_title, feed_item_id,
    saved_workout_id, completed, workout_rating, rpe, notes.
    Use this for scanning history and finding sessions — it's intentionally small.

    Set include_sets=True only when you need set-level exercise data AND you are querying
    a narrow range (1-3 days). For full set data on a single known session, prefer
    get_workout_details(program_workout_id, program_id) instead.
    """
    end = date.fromisoformat(end_date) if end_date else date.today()
    start = date.fromisoformat(start_date) if start_date else (date.today() - timedelta(weeks=weeks_back))
    client = _get_client()
    results = []
    current = start
    while current <= end:
        day_str = current.isoformat()
        day_results = client._get(
            "/3.0/athlete/programworkout/range",
            params={"startDate": day_str, "endDate": day_str, "preview": "false"},
        )
        results.extend(day_results)
        current += timedelta(days=1)
    if not include_sets:
        return [_project_history_item(w) for w in results]
    return [_trim_response(w) for w in results]


@mcp.tool()
def get_workout_details(
    program_workout_id: int,
    team_id: int | None = None,
    program_id: int | None = None,
) -> dict:
    """
    Get full workout details for a specific program workout including sets, exercises, and logged weights.

    Pass the program_workout_id from get_workout_history.
    To ensure the correct team is used, also pass program_id (the `program_id` field from the
    get_workout_history item) — the server will resolve the matching team automatically.
    Alternatively, pass team_id directly. Falls back to the user's primary team if neither is given.
    """
    c = _get_client()
    if team_id is None and program_id is not None:
        team_id = c.team_id_for_program(program_id)
    tid = team_id or c.team_id
    return _trim_response(c._get(f"/v5/programWorkouts/{program_workout_id}/teams/{tid}"))


@mcp.tool()
def get_exercise_stats(exercise_id: int, stat_date: str | None = None) -> dict:
    """
    Get stats for an exercise: last performance, personal record, and working max.

    stat_date is YYYY-MM-DD and defaults to today.
    Response includes isLift, lastPerformance (text, date, notes), personalRecord, and workingMax.
    """
    c = _get_client()
    d = stat_date or date.today().isoformat()
    return c._get(
        f"/v5/exercises/{exercise_id}/stats",
        params={"userId": c.user_id, "date": d},
    )


@mcp.tool()
def get_personal_records(exercise_id: int) -> list:
    """
    Get all personal records for an exercise, broken down by rep count.

    Each entry contains reps, weight, scaledWeight, units, and setNumber.
    """
    return _get_client()._get(f"/v5/exercises/{exercise_id}/personalRecords")


@mcp.tool()
def get_working_max(exercise_id: int) -> dict:
    """
    Get the current working max for a specific exercise.

    Response: {value, hasReferenceMaxExercise, referenceMaxExercise}
    """
    c = _get_client()
    return c._get(f"/v5/users/{c.user_id}/workingMaxes/{exercise_id}")


# ── Priority 2: Exercise library ───────────────────────────────────────────────

@mcp.tool()
def get_exercise_library(team_id: int | None = None, query: str | None = None) -> list:
    """
    Get the full exercise library for a team.

    Optionally filter by name with `query` (case-insensitive substring match).
    Each exercise has id, title, prescription, param1Type, param2Type, videoUrl, hasVideo.
    """
    c = _get_client()
    exercises = c._get(
        "/v5/users/exercises",
        params={"teamId": team_id or c.team_id, "userId": c.user_id},
    )
    if query:
        q = query.lower()
        exercises = [e for e in exercises if q in e.get("title", "").lower()]
    return exercises


@mcp.tool()
def get_circuit_library(team_id: int | None = None) -> list:
    """
    Get the circuit library for a team.

    Each circuit has id, title, instructions, prescription, and exerciseIds.
    """
    c = _get_client()
    return c._get(
        "/v5/users/circuits",
        params={"teamId": team_id or c.team_id, "userId": c.user_id},
    )


@mcp.tool()
def get_recent_exercises() -> list:
    """Get the user's recently used exercises."""
    return _get_client()._get("/v5/users/exercises/recent")


@mcp.tool()
def get_recent_circuits() -> list:
    """Get the user's recently used circuits."""
    return _get_client()._get("/v5/users/circuits/recent")


# ── Priority 3: Session management ────────────────────────────────────────────

@mcp.tool()
def create_personal_session(session_date: str) -> dict:
    """
    Create a new personal training session for a given date (YYYY-MM-DD).

    Returns {programWorkout: {id, programId, date, workoutId}, savedWorkout: {id}}.
    Use the returned workoutId with add_exercises_to_session and savedWorkout.id with log_workout.
    """
    return _get_client()._post("/v5/programWorkouts/personal", {"date": session_date})


@mcp.tool()
def add_exercises_to_session(workout_id: int, exercise_ids: list[int]) -> list:
    """
    Add exercises to a personal workout session in order.

    exercise_ids: ordered list of exercise IDs to add (use get_exercise_library to look up IDs).
    Returns the created workout sets with full exercise details.
    """
    body = {
        "exercises": [
            {"exerciseId": eid, "order": i + 1}
            for i, eid in enumerate(exercise_ids)
        ],
        "circuits": [],
    }
    return _get_client()._put(
        f"/v5/personalCalendar/workouts/{workout_id}/addExercises", body
    )


@mcp.tool()
def log_workout(
    saved_workout_id: int,
    workout_id: int,
    date_string: str,
    blocks: list[str],
    notes: str | None = None,
    rpe: int | None = None,
    workout_rating: str | None = None,
    is_personal_calendar: bool = True,
) -> dict:
    """
    Save/log a completed workout with results.

    saved_workout_id: from create_personal_session or get_workout_details.
    workout_id: the workout's workoutId.
    date_string: YYYY-MM-DD date of the session.
    blocks: list of block/set IDs that were completed.
    rpe: Rate of Perceived Exertion (1-10).
    workout_rating: numeric rating as string e.g. "8.0".
    """
    c = _get_client()
    body: dict = {
        "id": saved_workout_id,
        "workoutId": workout_id,
        "teamId": c.team_id,
        "date": f"{date_string}T00:00:00.000Z",
        "dateString": date_string,
        "blocks": blocks,
        "athleteFullName": c.full_name,
        "isPersonalCalendar": is_personal_calendar,
        "teamName": c.team_name,
    }
    if notes is not None:
        body["notes"] = notes
    if rpe is not None:
        body["rpe"] = rpe
    if workout_rating is not None:
        body["workout_rating"] = workout_rating
    return c._put(f"/1.0/athlete/savedworkout/{saved_workout_id}", body)


@mcp.tool()
def delete_session(program_workout_id: int) -> dict:
    """Delete a program workout / personal session by its ID."""
    return _get_client()._delete(f"/v5/programWorkouts/{program_workout_id}")


# ── Priority 4: Surveys & Messaging ───────────────────────────────────────────

@mcp.tool()
def get_workout_surveys(saved_workout_ids: list[int]) -> dict:
    """
    Get pre/post workout surveys for one or more saved workout IDs.

    Returns a map of savedWorkoutId → survey data with Sleep, Mood, Energy, Soreness, Stress questions.
    """
    return _get_client()._get(
        "/3.0/athlete/savedworkout/surveys",
        params={"swIds": json.dumps(saved_workout_ids)},
    )


@mcp.tool()
def submit_survey(saved_workout_id: int, question_id: int, answer_id: int) -> dict:
    """
    Submit a readiness/recovery survey answer for a workout.

    Question IDs: 8=Sleep, 9=Mood, 10=Energy, 11=Soreness, 12=Stress
    Answer IDs:   1=Awful/VeryPoor, 2=Poor, 3=Ok, 4=Good, 5=Excellent
    """
    return _get_client()._post(
        f"/3.0/athlete/survey/question/{question_id}",
        {"saved_workout_id": saved_workout_id, "survey_question_answer_id": answer_id},
    )


@mcp.tool()
def get_workout_messages(program_workout_id: int, team_id: int | None = None) -> dict:
    """
    Get the messaging stream and all comments for a workout.

    Returns {stream: {id, title, lastActivity, ...}, comments: [...]} where each comment
    has content, authorName, replies, and reactions.
    """
    c = _get_client()
    tid = team_id or c.team_id
    stream = c._get(f"/v5/messaging/streams/programWorkouts/{program_workout_id}/{tid}")
    stream_id = stream["id"]
    comments = c._get(
        f"/v5/messaging/streams/{stream_id}/comments",
        params={"lastCommentId": ""},
    )
    return {"stream": stream, "comments": comments}


@mcp.tool()
def get_workout_leaderboard(program_workout_id: int) -> dict:
    """
    Get the leaderboard for a specific program workout.

    Returns {workoutId, workoutTitle, date, tests, results, testStats, userResult}.
    """
    return _get_client()._get(
        f"/3.0/athlete/leaderboard/{program_workout_id}",
        params={"page": 1, "pageSize": 9999, "gender": 0},
    )


def _run_http() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    if not _auth_token:
        log.warning("MCP_AUTH_TOKEN is not set — the HTTP server is open to anyone!")
    log.info(f"HTTP transport — listening on 0.0.0.0:{port}/mcp")
    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    if os.getenv("MCP_TRANSPORT") == "http":
        _run_http()
    else:
        mcp.run(transport="stdio")
