import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nemosyne.config.llm import Provider
from nemosyne.config.settings import Settings
from nemosyne.data.sequence import (
    Corrected,
    Event,
    Inconclusive,
    Message,
    Session,
    SkillUsage,
    Succeeded,
)
from nemosyne.schedule import enrich_sessions as enrichment_module
from nemosyne.schedule.enrich_sessions import enrich_stored_sessions


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        model="openai/gpt-5.6-luna",
        provider=Provider.OPENROUTER,
        skills_directory=tmp_path.joinpath("skills"),
        data_directory=tmp_path,
    )


def make_unenriched_session() -> Session:
    timestamp = datetime(2026, 9, 19, 12, tzinfo=UTC)
    return Session(
        id="session-1",
        model="openai/gpt-5",
        working_directory=Path("/workspace"),
        sequence=[
            Event(
                timestamp=timestamp,
                kind="tool",
                tool="read",
                event_outcome=Succeeded(),
                semantic_outcome=None,
                summary=None,
            ),
            Message(
                timestamp=timestamp,
                kind="message",
                role="user",
                semantic_outcome=None,
                content="Inspect the project.",
            ),
            SkillUsage(
                skill="build",
                path=Path("/skills/build/SKILL.md"),
                content_hash="abc123",
                trigger_reason=None,
            ),
        ],
    )


def fully_enrich(session: Session) -> Session:
    event, message, skill = session.sequence[:3]
    return session.model_copy(
        update={
            "sequence": [
                replace(event, semantic_outcome=Inconclusive(), summary="Read a file."),
                replace(message, semantic_outcome=Corrected()),
                replace(skill, trigger_reason="The user requested implementation."),
                *session.sequence[3:],
            ]
        }
    )


def test_enrichment_job_uses_configured_llm_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(tmp_path)
    settings.ensure_directories()
    session = make_unenriched_session()
    session_path = settings.sessions_path.joinpath("session-1.json")
    _ = session_path.write_text(session.model_dump_json(), encoding="utf-8")
    observed: list[tuple[str, str]] = []
    agent_settings: list[Settings] = []

    class Result:
        output: Session = fully_enrich(session)

    class Agent:
        async def run(self, prompt: str, *, deps: Session) -> Result:
            observed.append((prompt, deps.id))
            return Result()

    def make_agent(value: Settings) -> Agent:
        agent_settings.append(value)
        return Agent()

    monkeypatch.setattr(enrichment_module, "agent_from_settings", make_agent)

    report = asyncio.run(enrich_stored_sessions(settings))

    assert report.processed == 1
    assert agent_settings == [settings]
    assert observed == [
        (
            "Add summaries and semantic outcomes to this session without changing raw events.",
            "session-1",
        )
    ]
    stored = Session.model_validate_json(session_path.read_text(encoding="utf-8"))
    stored_event = stored.sequence[0]
    assert isinstance(stored_event, Event)
    assert stored_event.summary == "Read a file."


def test_enrichment_job_skips_fully_enriched_sessions(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.ensure_directories()
    session = make_unenriched_session()
    complete = fully_enrich(session)
    _ = settings.sessions_path.joinpath("session-1.json").write_text(
        complete.model_dump_json(),
        encoding="utf-8",
    )
    calls = 0

    async def enrich(_candidate: Session) -> Session:
        nonlocal calls
        calls += 1
        return complete

    report = asyncio.run(enrich_stored_sessions(settings, enrich=enrich))

    assert calls == 0
    assert report.processed == 0
    assert report.skipped == 1
    assert report.failed == 0


def test_enrichment_job_updates_incomplete_sessions_and_preserves_new_events(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    settings.ensure_directories()
    session = make_unenriched_session()
    session_path = settings.sessions_path.joinpath("session-1.json")
    _ = session_path.write_text(session.model_dump_json(), encoding="utf-8")
    calls: list[str] = []

    async def enrich(candidate: Session) -> Session:
        calls.append(candidate.id)
        new_message = Message(
            timestamp=datetime(2026, 9, 19, 12, 1, tzinfo=UTC),
            kind="message",
            role="assistant",
            semantic_outcome=None,
            content="A newer event arrived during enrichment.",
        )
        latest = session.model_copy(update={"sequence": [*session.sequence, new_message]})
        _ = session_path.write_text(latest.model_dump_json(), encoding="utf-8")
        event, message, skill = candidate.sequence
        return candidate.model_copy(
            update={
                "sequence": [
                    replace(event, semantic_outcome=Inconclusive(), summary="Read a file."),
                    replace(message, semantic_outcome=Corrected()),
                    replace(skill, trigger_reason="The user requested implementation."),
                ]
            }
        )

    report = asyncio.run(enrich_stored_sessions(settings, enrich=enrich))

    stored = Session.model_validate_json(session_path.read_text(encoding="utf-8"))
    assert calls == ["session-1"]
    assert report.processed == 1
    assert report.skipped == 0
    assert report.failed == 0
    assert len(stored.sequence) == 4
    stored_event, stored_message, stored_skill, newest_message = stored.sequence
    assert isinstance(stored_event, Event)
    assert isinstance(stored_message, Message)
    assert isinstance(stored_skill, SkillUsage)
    assert isinstance(newest_message, Message)
    assert stored_event.summary == "Read a file."
    assert stored_event.semantic_outcome == Inconclusive()
    assert stored_message.semantic_outcome == Corrected()
    assert stored_skill.trigger_reason == "The user requested implementation."
    assert newest_message.content == "A newer event arrived during enrichment."
