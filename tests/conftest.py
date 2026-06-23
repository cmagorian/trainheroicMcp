import pytest

import trainheroic_mcp.server as server_module
from trainheroic_mcp.client import TrainHeroicClient
from tests.helpers import add_init_responses


@pytest.fixture(autouse=True)
def isolated_token_cache(tmp_path, monkeypatch):
    """Redirect TOKEN_CACHE_PATH and CACHE_DIR to per-test temp paths so tests
    never read or write the real ~/.config/trainheroic/ files."""
    monkeypatch.setattr(
        "trainheroic_mcp.client.TOKEN_CACHE_PATH", tmp_path / "session.json"
    )
    monkeypatch.setattr(
        "trainheroic_mcp.client.CACHE_DIR", tmp_path / "cache"
    )


@pytest.fixture
def th_client(httpx_mock):
    """Fully initialised TrainHeroicClient with init HTTP calls mocked."""
    add_init_responses(httpx_mock)
    return TrainHeroicClient(session_token="test-token")


@pytest.fixture
def patched_server(th_client, monkeypatch):
    """Sets server._client to th_client so tool functions use the mocked client."""
    monkeypatch.setattr(server_module, "_client", th_client)
    return th_client
