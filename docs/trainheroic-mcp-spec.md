# TrainHeroic MCP Server — Build Spec

## Overview

Build a Model Context Protocol (MCP) server that wraps the TrainHeroic mobile API. All endpoints were discovered via mitmproxy capture of the official iOS app (v8.25.0). Authentication uses username/password to obtain a session token, which is then used for all subsequent requests.

---

## Authentication

### Login
The session token must be obtained by POSTing credentials. Try these candidates in order (the login endpoint was not captured but follows standard patterns):

**Candidate 1:**
```
POST https://api.trainheroic.com/v5/users/login
Content-Type: application/json

{"email": "user@example.com", "password": "password123"}
```

**Candidate 2:**
```
POST https://account.trainheroic.com/v5/users/login
```

**Candidate 3:**
```
POST https://api.trainheroic.com/1.0/users/login
```

The response will contain a `session_id` or `token` field. Store this as the `SESSION_TOKEN`.

If login endpoint discovery fails, fall back to accepting the session token as a direct config parameter (user grabs it from browser DevTools or mitmproxy).

### Request Headers (use on ALL requests)
```
session-token: {SESSION_TOKEN}
x-mobile-app-version: 8.25.0
user-agent: TrainHeroic/82515396 CFNetwork/3860.600.12 Darwin/25.5.0
accept: */*
accept-language: en-US,en;q=0.9
content-type: application/json  (for POST/PUT only)
```

**Do NOT include** `Api-Token`, `Origin`, or `Referer` — these are web-only headers that break the mobile API.

### Base URL
```
https://api.trainheroic.com
```

---

## Confirmed Working Endpoints

### User / Profile

#### Get current user profile
```
GET /v5/user
```
Response: `{id, nameFirst, nameLast, profileImage, isCoachUser, isTrialCoach, ...}`

#### Get user features/flags
```
GET /v5/users/{userId}/features
```
Response: feature flag map (shows which features are enabled for this user)

#### Get Athlete Pro access status
```
GET /v5/athletePro/access
```
Response: `{hasAthleteProAccess, expiresAtTimestamp, athleteTrial, settings}`

#### Get notification counts
```
GET /v5/notifications/counts
```
Response: `{countNotViewed, countNotificationNotViewed, countMessagingNotViewed, messaging}`

---

### Teams / License

#### Get athlete license/team memberships
```
GET /1.0/athlete/userlicense/
```
Response: `{licenses: {team, team_share, coach, org, unlicensed: [{id, title, programId, coaches, ...}]}}`

Key fields:
- `id` = team ID (use as `TEAM_ID`)
- `programId` = program ID (use as `PROGRAM_ID`)
- `coaches[].id` = coach user ID

---

### Workout Calendar / History

#### Get workouts by date range ⭐ PRIMARY ENDPOINT
```
GET /3.0/athlete/programworkout/range?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&preview=false
```
Response: Array of program workouts with full details:
```json
[{
  "id": 149083689,
  "program_id": 4158000,
  "workout_id": 147480952,
  "workout_title": "Upper Dynamic .1",
  "year": 2026, "month": 5, "day": 31,
  "date": "2026-05-31",
  "feed_item_id": 124026322,
  "summarizedSavedWorkout": {
    "workout": {
      "id": 147480952,
      "title": "Upper Dynamic .1",
      "instruction": "...",
    },
    "saved_workout": {
      "id": 344342537,
      "completed": 1,
      "workout_rating": "8.0",
      "notes": "...",
      "rpe": 7,
      "workoutSets": [...]
    }
  }
}]
```

#### Get workout details for a specific program workout + team
```
GET /v5/programWorkouts/{programWorkoutId}/teams/{teamId}
```
Response: Full saved workout with sets, exercises, logged weights

#### Get pre/post workout surveys for saved workouts
```
GET /3.0/athlete/savedworkout/surveys?swIds=[id1,id2,id3]
```
Note: URL-encode the array: `swIds=%5B344342537%5D`
Response: Map of savedWorkoutId → survey with questions (Sleep, Mood, Energy, Soreness, Stress)

#### Get leaderboard for a workout
```
GET /3.0/athlete/leaderboard/{programWorkoutId}?page=1&pageSize=9999&gender=0
```
Response: `{workoutId, workoutTitle, date, tests, results, testStats, userResult}`

---

### Personal Calendar (athlete-created sessions)

#### Create a personal session
```
POST /v5/programWorkouts/personal
{"date": "2026-05-27"}
```
Response: `{programWorkout: {id, programId, date, workoutId, ...}, savedWorkout: {id, ...}}`

#### Delete a program workout
```
DELETE /v5/programWorkouts/{programWorkoutId}
```

#### Add exercises to a personal workout
```
PUT /v5/personalCalendar/workouts/{workoutId}/addExercises
{
  "exercises": [
    {"exerciseId": 7997728, "order": 1},
    {"exerciseId": 7096311, "order": 2}
  ],
  "circuits": []
}
```
Response: Array of created workout sets with exercise details

#### Save/log a workout (record results)
```
PUT /1.0/athlete/savedworkout/{savedWorkoutId}
{
  "id": 345362535,
  "workoutId": 148049813,
  "teamId": 4122385,
  "date": "2026-05-27T00:00:00.000Z",
  "dateString": "2026-05-27",
  "blocks": ["blockId1", "blockId2"],
  "athleteFullName": "Christopher Magorian",
  "isPersonalCalendar": true,
  "teamName": "Christopher Magorian",
  ...
}
```

---

### Exercises

#### Get exercise library for team
```
GET /v5/users/exercises?teamId={teamId}&userId={userId}
```
Response: Array of exercises with `{id, title, prescription, param1Type, param2Type, videoUrl, hasVideo}`

#### Get circuit library for team
```
GET /v5/users/circuits?teamId={teamId}&userId={userId}
```
Response: Array of circuits with `{id, title, instructions, prescription, exerciseIds}`

#### Get recently used exercises
```
GET /v5/users/exercises/recent
```

#### Get recently used circuits
```
GET /v5/users/circuits/recent
```

#### Get exercise stats (last performance + PR + working max)
```
GET /v5/exercises/{exerciseId}/stats?userId={userId}&date=YYYY-MM-DD&
```
Response:
```json
{
  "isLift": true,
  "lastPerformance": {
    "text": "3 x 6 @ 165 lb",
    "dateCompleted": "2026-05-29",
    "notes": "...",
    "savedWorkoutSetExercise": {...}
  },
  "personalRecord": {"value": 165, "dateCompleted": "...", "units": "lb"},
  "workingMax": {"value": 194, "units": "lb"}
}
```

#### Get personal records for an exercise
```
GET /v5/exercises/{exerciseId}/personalRecords
```
Response: Array of PRs by rep count `[{reps, weight, scaledWeight, units, setNumber}]`

#### Check if exercise has StackUp leaderboard support
```
GET /v5/exercises/{exerciseId}/stackUp/isSupportedExercise
```
Response: `{"isSupportedExercise": true}`

---

### Working Maxes

#### Get working max for specific exercise
```
GET /v5/users/{userId}/workingMaxes/{exerciseId}
```
Response: `{"value": 194, "hasReferenceMaxExercise": false, "referenceMaxExercise": null}`

---

### Surveys (pre-workout readiness)

#### Submit a survey question answer
```
POST /3.0/athlete/survey/question/{questionId}
{"saved_workout_id": 345362535, "survey_question_answer_id": 36}
```
Question IDs: 8=Sleep, 9=Mood, 10=Energy, 11=Soreness, 12=Stress
Answer IDs (per question): 1=Awful/VeryPoor, 2=Poor, 3=Ok, 4=Good, 5=Excellent

---

### Messaging

#### Get messaging stream for a workout
```
GET /v5/messaging/streams/programWorkouts/{programWorkoutId}/{teamId}
```
Response: `{id: streamId, teamId, title, lastActivity, lastViewed, programWorkoutId}`

#### Get comments in a stream
```
GET /v5/messaging/streams/{streamId}/comments?lastCommentId=
```
Response: Array of comments with `{id, content, imageUrl, thumbnailUrl, authorName, replies, reactions}`

---

## Known Limitations

- `GET /v5/users/goals/lifts` — requires **Athlete Pro** subscription (returns 401)
- `GET /v5/calendars/athletes/{id}/nutrition` — requires **Athlete Pro**
- `GET /v5/programs` — coach-only (returns 401 "Coach account required")
- `POST /v5/users/dataExport` — broken on backend (504 timeout)

---

## MCP Tools to Implement

### Priority 1 (core data)
1. `get_workout_history(start_date, end_date)` → calls `/3.0/athlete/programworkout/range`
2. `get_workout_details(program_workout_id, team_id)` → calls `/v5/programWorkouts/{id}/teams/{teamId}`
3. `get_exercise_stats(exercise_id, date?)` → calls `/v5/exercises/{id}/stats`
4. `get_personal_records(exercise_id)` → calls `/v5/exercises/{id}/personalRecords`
5. `get_working_max(exercise_id)` → calls `/v5/users/{userId}/workingMaxes/{exerciseId}`
6. `get_user_profile()` → calls `/v5/user`
7. `get_team_info()` → calls `/1.0/athlete/userlicense/`

### Priority 2 (exercise library)
8. `get_exercise_library(team_id?)` → calls `/v5/users/exercises`
9. `get_circuit_library(team_id?)` → calls `/v5/users/circuits`
10. `get_recent_exercises()` → calls `/v5/users/exercises/recent`
11. `get_recent_circuits()` → calls `/v5/users/circuits/recent`

### Priority 3 (session management)
12. `create_personal_session(date)` → calls `POST /v5/programWorkouts/personal`
13. `add_exercises_to_session(workout_id, exercise_ids)` → calls `PUT /v5/personalCalendar/workouts/{id}/addExercises`
14. `log_workout(saved_workout_id, blocks)` → calls `PUT /1.0/athlete/savedworkout/{id}`
15. `delete_session(program_workout_id)` → calls `DELETE /v5/programWorkouts/{id}`

### Priority 4 (surveys & messaging)
16. `get_workout_surveys(saved_workout_ids)` → calls `/3.0/athlete/savedworkout/surveys`
17. `submit_survey(saved_workout_id, question_id, answer_id)` → calls `POST /3.0/athlete/survey/question/{id}`
18. `get_workout_messages(program_workout_id, team_id)` → calls messaging streams endpoints
19. `get_workout_leaderboard(program_workout_id)` → calls `/3.0/athlete/leaderboard/{id}`

---

## Implementation Notes

### Auth flow
```python
class TrainHeroicClient:
    def __init__(self, email=None, password=None, session_token=None):
        if session_token:
            self.token = session_token
        elif email and password:
            self.token = self._login(email, password)
        else:
            raise ValueError("Provide either session_token or email+password")
        
        self.headers = {
            "session-token": self.token,
            "x-mobile-app-version": "8.25.0",
            "user-agent": "TrainHeroic/82515396 CFNetwork/3860.600.12 Darwin/25.5.0",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
        }
        # Fetch and cache user profile + team IDs on init
        profile = self._get("/v5/user")
        self.user_id = profile["id"]
        licenses = self._get("/1.0/athlete/userlicense/")
        teams = licenses["licenses"].get("unlicensed", []) + licenses["licenses"].get("team", [])
        self.team_id = teams[0]["id"] if teams else None
        self.program_id = teams[0]["programId"] if teams else None
```

### Token caching
Cache the session token to disk (e.g. `~/.trainheroic_session`) to avoid re-login on every MCP startup. Check if token is still valid by calling `/v5/user` — if 401, re-login.

### Date range helpers
When fetching history, default to last 30 days. Allow `weeks_back` or explicit `start_date/end_date` params.

### Exercise ID lookup
The exercise library endpoint returns all exercises. Cache this on startup and allow lookup by name (fuzzy match) or ID.

---

## Config (environment variables or config file)
```
TRAINHEROIC_EMAIL=user@example.com
TRAINHEROIC_PASSWORD=password123
# OR
TRAINHEROIC_SESSION_TOKEN=2a2f35ce349afe9bb06bb6a21d58a455
```

---

## Recommended Stack
- **Language:** Python 3.11+
- **MCP SDK:** `mcp` (official Python SDK from Anthropic)
- **HTTP:** `httpx` (async) or `requests`
- **Token storage:** `keyring` or simple JSON file in `~/.config/trainheroic/`
