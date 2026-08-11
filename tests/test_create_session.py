from fastapi.testclient import TestClient

from nemosyne.cli.daemon import app

client = TestClient(app)


def test_accept_session() -> None:
    payload = {
        "id": "session-1",
        "model": "gpt-5",
        "working_directory": "/tmp/project",
        "sequence": [
            {
                "timestamp": "2026-08-10T18:00:00Z",
                "kind": "tool",
                "tool": "read",
                "event_outcome": {"tag": "Inconclusive"},
            }
        ],
    }

    response = client.post("/sessions", json=payload)

    assert response.status_code == 200
    assert response.json()
