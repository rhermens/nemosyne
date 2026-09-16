from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from nemosyne.config.llm import Provider
from nemosyne.config.settings import Settings
from nemosyne.data.sequence import Session
from nemosyne.mcp import sessions


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[ClientSession]:
    settings = Settings(
        model="openai/gpt-5.6-luna",
        provider=Provider.OPENROUTER,
        skills_directory=tmp_path.joinpath("skills"),
        data_directory=tmp_path,
    )
    monkeypatch.setattr(sessions, "get_settings", lambda: settings)

    async with create_connected_server_and_client_session(
        sessions.mcp, raise_exceptions=True
    ) as session:
        yield session


@pytest.mark.anyio
async def test_store_session_tool(
    client_session: ClientSession, tmp_path: Path
) -> None:
    payload = {
        "id": "session-1",
        "model": "gpt-5",
        "working_directory": str(tmp_path.joinpath("project")),
        "sequence": [
            {
                "timestamp": "2026-08-10T18:00:00Z",
                "kind": "tool",
                "tool": "read",
                "event_outcome": {"tag": "Inconclusive"},
            }
        ],
    }

    result = await client_session.call_tool("store_session", payload)

    assert not result.isError
    assert result.structuredContent == {
        "session_id": "session-1",
        "stored": True,
        "duplicate": False,
    }
    stored = Session.model_validate_json(
        tmp_path.joinpath("sessions/session-1.json").read_text(encoding="utf-8")
    )
    assert stored.id == "session-1"
    assert stored.model == "gpt-5"

    duplicate = await client_session.call_tool("store_session", payload)

    assert not duplicate.isError
    assert duplicate.structuredContent == {
        "session_id": "session-1",
        "stored": False,
        "duplicate": True,
    }
