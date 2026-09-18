from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from nemosyne.cli.daemon import app
from nemosyne.config.llm import Provider
from nemosyne.config.settings import Settings, get_settings
from nemosyne.data.sequence import Message, Session


@pytest.fixture
def session_payload(tmp_path: Path) -> dict[str, object]:
    return {
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


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient]:
    settings = Settings(
        model="openai/gpt-5.6-luna",
        provider=Provider.OPENROUTER,
        skills_directory=tmp_path.joinpath("skills"),
        data_directory=tmp_path,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_store_session(
    client: TestClient,
    tmp_path: Path,
    session_payload: dict[str, object],
) -> None:
    response = client.post("/sessions", json=session_payload)

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-1",
        "stored": True,
        "duplicate": False,
    }
    stored = Session.model_validate_json(
        tmp_path.joinpath("sessions/session-1.json").read_text(encoding="utf-8")
    )
    assert stored.id == "session-1"
    assert stored.model == "gpt-5"


def test_store_session_persists_messages(
    client: TestClient,
    tmp_path: Path,
    session_payload: dict[str, object],
) -> None:
    message = {
        "timestamp": "2026-08-10T18:00:01Z",
        "kind": "message",
        "role": "user",
        "content": "Please inspect the session.",
    }
    sequence_value = session_payload["sequence"]
    assert isinstance(sequence_value, list)
    sequence = cast(list[dict[str, object]], sequence_value)
    payload: dict[str, object] = {
        **session_payload,
        "sequence": [*sequence, message],
    }

    response = client.post("/sessions", json=payload)

    assert response.status_code == 200
    stored = Session.model_validate_json(
        tmp_path.joinpath("sessions/session-1.json").read_text(encoding="utf-8")
    )
    stored_message = stored.sequence[1]
    assert isinstance(stored_message, Message)
    assert stored_message.role == "user"
    assert stored_message.content == "Please inspect the session."


def test_store_session_is_idempotent(
    client: TestClient,
    session_payload: dict[str, object],
) -> None:
    first_response = client.post("/sessions", json=session_payload)
    duplicate_response = client.post("/sessions", json=session_payload)

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 200
    assert duplicate_response.json() == {
        "session_id": "session-1",
        "stored": False,
        "duplicate": True,
    }


def test_store_session_updates_a_settled_session(
    client: TestClient,
    tmp_path: Path,
    session_payload: dict[str, object],
) -> None:
    first_response = client.post("/sessions", json=session_payload)
    updated_payload = {**session_payload, "model": "different-model"}
    updated_response = client.post("/sessions", json=updated_payload)

    assert first_response.status_code == 200
    assert updated_response.status_code == 200
    assert updated_response.json() == {
        "session_id": "session-1",
        "stored": True,
        "duplicate": False,
    }
    stored = Session.model_validate_json(
        tmp_path.joinpath("sessions/session-1.json").read_text(encoding="utf-8")
    )
    assert stored.model == "different-model"
