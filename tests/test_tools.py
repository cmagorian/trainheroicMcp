"""
Tool-level tests: each tool function is called directly with server._client
patched to a fully-initialised mock client (via the `patched_server` fixture).
"""

import json
import re

import pytest

import trainheroic_mcp.server as server
from tests.helpers import BASE, MOCK_EXERCISES, MOCK_CIRCUITS, MOCK_LICENSE, MOCK_PROFILE


# ── Priority 1: Core data ──────────────────────────────────────────────────────

class TestGetUserProfile:
    def test_returns_profile(self, patched_server, httpx_mock):
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", json=MOCK_PROFILE)
        result = server.get_user_profile()
        assert result["id"] == 42

    def test_calls_correct_endpoint(self, patched_server, httpx_mock):
        httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", json=MOCK_PROFILE)
        server.get_user_profile()
        req = httpx_mock.get_requests()[-1]
        assert req.url.path == "/v5/user"
        assert req.method == "GET"


class TestGetTeamInfo:
    def test_returns_license_data(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET", url=f"{BASE}/1.0/athlete/userlicense/", json=MOCK_LICENSE
        )
        result = server.get_team_info()
        assert "licenses" in result


class TestGetWorkoutHistory:
    @staticmethod
    def _range_reqs(httpx_mock):
        return [r for r in httpx_mock.get_requests() if "programworkout/range" in str(r.url)]

    def test_fetches_one_request_per_day(self, patched_server, httpx_mock):
        for _ in range(3):
            httpx_mock.add_response(
                method="GET",
                url=re.compile(r".*/3\.0/athlete/programworkout/range.*"),
                json=[],
            )
        server.get_workout_history(start_date="2026-01-01", end_date="2026-01-03")
        reqs = self._range_reqs(httpx_mock)
        assert len(reqs) == 3
        assert reqs[0].url.params["startDate"] == "2026-01-01"
        assert reqs[0].url.params["endDate"] == "2026-01-01"
        assert reqs[2].url.params["startDate"] == "2026-01-03"
        assert reqs[2].url.params["endDate"] == "2026-01-03"

    def test_each_day_request_uses_single_day_range(self, patched_server, httpx_mock):
        for _ in range(2):
            httpx_mock.add_response(
                method="GET",
                url=re.compile(r".*/3\.0/athlete/programworkout/range.*"),
                json=[],
            )
        server.get_workout_history(start_date="2026-01-01", end_date="2026-01-02")
        for req in self._range_reqs(httpx_mock):
            assert req.url.params["startDate"] == req.url.params["endDate"]
            assert req.url.params["preview"] == "false"

    def test_results_from_all_days_are_combined(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/3\.0/athlete/programworkout/range.*"),
            json=[{"id": 1, "date": "2026-01-01"}],
        )
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/3\.0/athlete/programworkout/range.*"),
            json=[{"id": 2, "date": "2026-01-02"}],
        )
        result = server.get_workout_history(start_date="2026-01-01", end_date="2026-01-02")
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    def test_weeks_back_sets_correct_start_date(self, patched_server, httpx_mock):
        from datetime import date, timedelta
        # weeks_back=1: 8 days inclusive (today-7 through today)
        num_days = (date.today() - (date.today() - timedelta(weeks=1))).days + 1
        for _ in range(num_days):
            httpx_mock.add_response(
                method="GET",
                url=re.compile(r".*/3\.0/athlete/programworkout/range.*"),
                json=[],
            )
        server.get_workout_history(weeks_back=1)
        reqs = self._range_reqs(httpx_mock)
        assert len(reqs) == num_days
        expected_start = (date.today() - timedelta(weeks=1)).isoformat()
        assert reqs[0].url.params["startDate"] == expected_start

    def _api_workout(self, workout_id: int) -> dict:
        return {
            "id": workout_id,
            "workout_id": 200,
            "program_id": 2001,
            "date": "2026-01-01",
            "workout_title": "Leg Day",
            "feed_item_id": 300,
            "summarizedSavedWorkout": {
                "workout": {"id": 200, "title": "Leg Day", "instruction": "lots of text..."},
                "saved_workout": {
                    "id": 400,
                    "completed": 1,
                    "rpe": 7,
                    "workout_rating": "8.0",
                    "notes": "felt good",
                    "workoutSets": [{"setId": 1, "weight": 135, "videoUrl": "https://..."}],
                },
            },
        }

    def test_default_projects_to_flat_summary(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/3\.0/athlete/programworkout/range.*"),
            json=[self._api_workout(1)],
        )
        result = server.get_workout_history(start_date="2026-01-01", end_date="2026-01-01")
        item = result[0]
        assert item["id"] == 1
        assert item["date"] == "2026-01-01"
        assert item["workout_title"] == "Leg Day"
        assert item["saved_workout_id"] == 400
        assert item["rpe"] == 7
        assert item["notes"] == "felt good"
        assert "summarizedSavedWorkout" not in item
        assert "workoutSets" not in item

    def test_include_sets_returns_sets_without_media_fields(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/3\.0/athlete/programworkout/range.*"),
            json=[self._api_workout(1)],
        )
        result = server.get_workout_history(
            start_date="2026-01-01", end_date="2026-01-01", include_sets=True
        )
        sw = result[0]["summarizedSavedWorkout"]["saved_workout"]
        assert "workoutSets" in sw
        assert sw["workoutSets"][0]["weight"] == 135
        assert "videoUrl" not in sw["workoutSets"][0]

    def test_sessions_without_summarized_workout_pass_through(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/3\.0/athlete/programworkout/range.*"),
            json=[{"id": 99, "date": "2026-01-01"}],
        )
        result = server.get_workout_history(start_date="2026-01-01", end_date="2026-01-01")
        assert result[0]["id"] == 99
        assert result[0]["date"] == "2026-01-01"


class TestGetWorkoutDetails:
    def test_constructs_url_with_ids(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/programWorkouts/555/teams/1001.*"),
            json={"id": 555},
        )
        result = server.get_workout_details(program_workout_id=555)
        assert result["id"] == 555

    def test_uses_client_team_id_by_default(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/programWorkouts/\d+/teams/1001.*"),
            json={},
        )
        server.get_workout_details(program_workout_id=123)
        req = httpx_mock.get_requests()[-1]
        assert "/teams/1001" in req.url.path

    def test_explicit_team_id_overrides_default(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/programWorkouts/\d+/teams/9999.*"),
            json={},
        )
        server.get_workout_details(program_workout_id=123, team_id=9999)
        req = httpx_mock.get_requests()[-1]
        assert "/teams/9999" in req.url.path

    def test_program_id_resolves_to_matching_team(self, patched_server, httpx_mock):
        # patched_server has team_id=1001 for program_id=2001 (from MOCK_LICENSE)
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/programWorkouts/\d+/teams/1001.*"),
            json={},
        )
        server.get_workout_details(program_workout_id=123, program_id=2001)
        req = httpx_mock.get_requests()[-1]
        assert "/teams/1001" in req.url.path

    def test_media_fields_stripped_from_response(self, patched_server, httpx_mock):
        api_payload = {
            "saved_workout": {
                "id": 700,
                "workoutSets": [
                    {
                        "exercise": {
                            "id": 77,
                            "title": "Bench Press",
                            "videoUrl": "https://cdn.example.com/video.mp4",
                            "thumbnailUrl": "https://cdn.example.com/thumb.jpg",
                            "hasVideo": True,
                        },
                        "weight": 185,
                        "reps": 5,
                    }
                ],
            }
        }
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/programWorkouts/555/teams/1001.*"),
            json=api_payload,
        )
        result = server.get_workout_details(program_workout_id=555)
        ex = result["saved_workout"]["workoutSets"][0]["exercise"]
        assert ex["title"] == "Bench Press"
        assert ex["id"] == 77
        assert "videoUrl" not in ex
        assert "thumbnailUrl" not in ex
        assert "hasVideo" not in ex
        assert result["saved_workout"]["workoutSets"][0]["weight"] == 185


class TestGetExerciseStats:
    def test_injects_user_id_from_client(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/exercises/77/stats.*"),
            json={"isLift": True},
        )
        server.get_exercise_stats(exercise_id=77)
        req = httpx_mock.get_requests()[-1]
        assert req.url.params["userId"] == "42"

    def test_explicit_date_passed_through(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/exercises/77/stats.*"),
            json={},
        )
        server.get_exercise_stats(exercise_id=77, stat_date="2026-03-15")
        req = httpx_mock.get_requests()[-1]
        assert req.url.params["date"] == "2026-03-15"


class TestGetPersonalRecords:
    def test_calls_correct_endpoint(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE}/v5/exercises/77/personalRecords",
            json=[{"reps": 1, "weight": 200}],
        )
        result = server.get_personal_records(exercise_id=77)
        assert result[0]["weight"] == 200


class TestGetWorkingMax:
    def test_injects_user_id_into_url(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE}/v5/users/42/workingMaxes/77",
            json={"value": 194},
        )
        result = server.get_working_max(exercise_id=77)
        assert result["value"] == 194


# ── Priority 2: Exercise library ───────────────────────────────────────────────

class TestGetExerciseLibrary:
    def test_returns_full_library(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/users/exercises.*"),
            json=MOCK_EXERCISES,
        )
        result = server.get_exercise_library()
        assert len(result) == 3

    def test_query_filters_by_name(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/users/exercises.*"),
            json=MOCK_EXERCISES,
        )
        result = server.get_exercise_library(query="squat")
        assert len(result) == 1
        assert result[0]["title"] == "Back Squat"

    def test_query_is_case_insensitive(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/users/exercises.*"),
            json=MOCK_EXERCISES,
        )
        result = server.get_exercise_library(query="BENCH")
        assert len(result) == 1
        assert result[0]["title"] == "Bench Press"

    def test_uses_client_team_id(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/users/exercises.*"),
            json=[],
        )
        server.get_exercise_library()
        req = httpx_mock.get_requests()[-1]
        assert req.url.params["teamId"] == "1001"
        assert req.url.params["userId"] == "42"


class TestGetCircuitLibrary:
    def test_returns_circuits(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/users/circuits.*"),
            json=MOCK_CIRCUITS,
        )
        result = server.get_circuit_library()
        assert result[0]["title"] == "Push Circuit"

    def test_uses_client_team_id(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/users/circuits.*"),
            json=[],
        )
        server.get_circuit_library()
        req = httpx_mock.get_requests()[-1]
        assert req.url.params["teamId"] == "1001"


class TestGetRecentExercises:
    def test_calls_correct_endpoint(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET", url=f"{BASE}/v5/users/exercises/recent", json=[]
        )
        server.get_recent_exercises()
        assert httpx_mock.get_requests()[-1].url.path == "/v5/users/exercises/recent"


class TestGetRecentCircuits:
    def test_calls_correct_endpoint(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET", url=f"{BASE}/v5/users/circuits/recent", json=[]
        )
        server.get_recent_circuits()
        assert httpx_mock.get_requests()[-1].url.path == "/v5/users/circuits/recent"


# ── Priority 3: Session management ────────────────────────────────────────────

class TestCreatePersonalSession:
    def test_posts_date(self, patched_server, httpx_mock):
        response_body = {
            "programWorkout": {"id": 500, "workoutId": 600},
            "savedWorkout": {"id": 700},
        }
        httpx_mock.add_response(
            method="POST", url=f"{BASE}/v5/programWorkouts/personal", json=response_body
        )
        result = server.create_personal_session("2026-06-15")
        req = httpx_mock.get_requests()[-1]
        assert json.loads(req.content) == {"date": "2026-06-15"}
        assert result["savedWorkout"]["id"] == 700


class TestAddExercisesToSession:
    def test_builds_ordered_exercise_body(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="PUT",
            url=f"{BASE}/v5/personalCalendar/workouts/600/addExercises",
            json=[],
        )
        server.add_exercises_to_session(workout_id=600, exercise_ids=[100, 101, 102])
        req = httpx_mock.get_requests()[-1]
        body = json.loads(req.content)
        assert body["exercises"] == [
            {"exerciseId": 100, "order": 1},
            {"exerciseId": 101, "order": 2},
            {"exerciseId": 102, "order": 3},
        ]
        assert body["circuits"] == []

    def test_single_exercise(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="PUT",
            url=f"{BASE}/v5/personalCalendar/workouts/600/addExercises",
            json=[],
        )
        server.add_exercises_to_session(workout_id=600, exercise_ids=[100])
        body = json.loads(httpx_mock.get_requests()[-1].content)
        assert body["exercises"][0]["order"] == 1


class TestLogWorkout:
    def test_injects_context_fields(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="PUT",
            url=f"{BASE}/1.0/athlete/savedworkout/700",
            json={"saved": True},
        )
        server.log_workout(
            saved_workout_id=700,
            workout_id=600,
            date_string="2026-06-15",
            blocks=["b1", "b2"],
        )
        body = json.loads(httpx_mock.get_requests()[-1].content)
        assert body["teamId"] == 1001
        assert body["athleteFullName"] == "Chris Magorian"
        assert body["teamName"] == "Team Alpha"

    def test_date_formatted_as_iso_string(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="PUT", url=f"{BASE}/1.0/athlete/savedworkout/700", json={}
        )
        server.log_workout(700, 600, "2026-06-15", [])
        body = json.loads(httpx_mock.get_requests()[-1].content)
        assert body["date"] == "2026-06-15T00:00:00.000Z"
        assert body["dateString"] == "2026-06-15"

    def test_optional_fields_included_when_provided(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="PUT", url=f"{BASE}/1.0/athlete/savedworkout/700", json={}
        )
        server.log_workout(700, 600, "2026-06-15", [], notes="Felt great", rpe=7, workout_rating="8.5")
        body = json.loads(httpx_mock.get_requests()[-1].content)
        assert body["notes"] == "Felt great"
        assert body["rpe"] == 7
        assert body["workout_rating"] == "8.5"

    def test_optional_fields_omitted_when_not_provided(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="PUT", url=f"{BASE}/1.0/athlete/savedworkout/700", json={}
        )
        server.log_workout(700, 600, "2026-06-15", [])
        body = json.loads(httpx_mock.get_requests()[-1].content)
        assert "notes" not in body
        assert "rpe" not in body
        assert "workout_rating" not in body


class TestDeleteSession:
    def test_calls_delete_on_correct_url(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE}/v5/programWorkouts/500",
            status_code=204,
            content=b"",
        )
        result = server.delete_session(program_workout_id=500)
        req = httpx_mock.get_requests()[-1]
        assert req.method == "DELETE"
        assert req.url.path == "/v5/programWorkouts/500"
        assert result == {}


# ── Priority 4: Surveys & Messaging ───────────────────────────────────────────

class TestGetWorkoutSurveys:
    def test_encodes_ids_as_json_array(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/3\.0/athlete/savedworkout/surveys.*"),
            json={"700": {}},
        )
        server.get_workout_surveys([700, 701])
        req = httpx_mock.get_requests()[-1]
        assert req.url.params["swIds"] == "[700, 701]"


class TestSubmitSurvey:
    def test_posts_to_question_endpoint(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE}/3.0/athlete/survey/question/8",
            json={"ok": True},
        )
        server.submit_survey(saved_workout_id=700, question_id=8, answer_id=4)
        req = httpx_mock.get_requests()[-1]
        body = json.loads(req.content)
        assert body["saved_workout_id"] == 700
        assert body["survey_question_answer_id"] == 4

    def test_question_id_in_url(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE}/3.0/athlete/survey/question/12",
            json={},
        )
        server.submit_survey(700, question_id=12, answer_id=2)
        req = httpx_mock.get_requests()[-1]
        assert "/question/12" in req.url.path


class TestGetWorkoutMessages:
    def test_fetches_stream_then_comments(self, patched_server, httpx_mock):
        stream = {"id": 888, "title": "Workout Chat", "programWorkoutId": 555}
        comments = [{"id": 1, "content": "Nice work!"}]
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE}/v5/messaging/streams/programWorkouts/555/1001",
            json=stream,
        )
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/messaging/streams/888/comments.*"),
            json=comments,
        )
        result = server.get_workout_messages(program_workout_id=555)
        assert result["stream"]["id"] == 888
        assert result["comments"][0]["content"] == "Nice work!"

    def test_uses_stream_id_from_first_response(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE}/v5/messaging/streams/programWorkouts/555/1001",
            json={"id": 999},
        )
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/v5/messaging/streams/999/comments.*"),
            json=[],
        )
        server.get_workout_messages(program_workout_id=555)
        reqs = httpx_mock.get_requests()
        assert "/streams/999/comments" in reqs[-1].url.path


class TestGetWorkoutLeaderboard:
    def test_passes_pagination_params(self, patched_server, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r".*/3\.0/athlete/leaderboard/555.*"),
            json={"results": []},
        )
        server.get_workout_leaderboard(program_workout_id=555)
        req = httpx_mock.get_requests()[-1]
        assert req.url.params["pageSize"] == "9999"
        assert req.url.params["page"] == "1"
        assert req.url.params["gender"] == "0"
