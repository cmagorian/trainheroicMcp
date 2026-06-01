"""Shared test constants and helpers (no pytest imports — safe to use anywhere)."""

BASE = "https://api.trainheroic.com"

MOCK_PROFILE = {
    "id": 42,
    "nameFirst": "Chris",
    "nameLast": "Magorian",
}

MOCK_LICENSE = {
    "licenses": {
        "team": [{"id": 1001, "programId": 2001, "title": "Team Alpha"}],
        "team_share": [],
        "unlicensed": [],
    }
}

MOCK_EXERCISES = [
    {"id": 100, "title": "Back Squat", "prescription": "weight", "hasVideo": True},
    {"id": 101, "title": "Bench Press", "prescription": "weight", "hasVideo": False},
    {"id": 102, "title": "Romanian Deadlift", "prescription": "weight", "hasVideo": True},
]

MOCK_CIRCUITS = [
    {"id": 200, "title": "Push Circuit", "instructions": "", "exerciseIds": [100, 101]},
]


def add_init_responses(httpx_mock) -> None:
    """Add the two HTTP responses every TrainHeroicClient.__init__ will consume."""
    httpx_mock.add_response(method="GET", url=f"{BASE}/v5/user", json=MOCK_PROFILE)
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/1.0/athlete/userlicense/",
        json=MOCK_LICENSE,
    )
