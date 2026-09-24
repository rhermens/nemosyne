import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nemosyne.config.llm import Provider
from nemosyne.config.settings import Settings
from nemosyne.data.annotation import (
    EventAnnotation,
    MessageAnnotation,
    SessionAnnotation,
    SkillUsageAnnotation,
)
from nemosyne.data.sequence import (
    Corrected,
    Event,
    Inconclusive,
    Message,
    Session,
    SkillUsage,
    Succeeded,
    TriggerReason,
)
from nemosyne.schedule import annotate_sessions as annotation_module
from nemosyne.schedule.annotate_sessions import (
    annotate_stored_sessions,
    merge_annotation,
)


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        model="openai/gpt-5.6-luna",
        provider=Provider.OPENROUTER,
        skills_directory=tmp_path.joinpath("skills"),
        data_directory=tmp_path,
    )


def make_unannotated_session() -> Session:
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


def make_annotation() -> SessionAnnotation:
    return SessionAnnotation(
        sequence=[
            EventAnnotation(index=0, semantic_outcome=Inconclusive()),
            MessageAnnotation(index=1, semantic_outcome=Corrected()),
            SkillUsageAnnotation(
                index=2,
                trigger_reason=TriggerReason.EXPLICIT_REQUEST,
            ),
        ]
    )


def fully_annotate(session: Session) -> Session:
    return merge_annotation(session, session, make_annotation())


def test_event_does_not_store_summary() -> None:
    event = make_unannotated_session().sequence[0]

    assert isinstance(event, Event)
    assert not hasattr(event, "summary")


def test_event_annotation_rejects_summary() -> None:
    with pytest.raises(ValueError):
        _ = EventAnnotation.model_validate(
            {
                "index": 0,
                "summary": "Read a file.",
                "semantic_outcome": Inconclusive(),
            }
        )


def test_skill_usage_annotation_rejects_free_text_trigger_reason() -> None:
    with pytest.raises(ValueError):
        _ = SkillUsageAnnotation.model_validate(
            {"index": 0, "trigger_reason": "The user requested implementation."}
        )


def test_session_annotation_rejects_session_metadata() -> None:
    with pytest.raises(ValueError):
        _ = SessionAnnotation.model_validate({"sequence": [], "id": "session-1"})


def test_session_annotation_rejects_duplicate_indexes() -> None:
    with pytest.raises(ValueError, match="indexes must be unique"):
        _ = SessionAnnotation(
            sequence=[
                MessageAnnotation(index=0, semantic_outcome=Corrected()),
                MessageAnnotation(index=0, semantic_outcome=Inconclusive()),
            ]
        )


def test_merge_annotation_accepts_generated_fields_without_raw_session_data() -> None:
    session = make_unannotated_session()

    annotation = SessionAnnotation(
        sequence=[
            EventAnnotation(index=0, semantic_outcome=Inconclusive()),
            MessageAnnotation(index=1, semantic_outcome=Corrected()),
            SkillUsageAnnotation(
                index=2,
                trigger_reason=TriggerReason.EXPLICIT_REQUEST,
            ),
        ]
    )

    merged = merge_annotation(session, session, annotation)

    event, message, skill = merged.sequence
    assert isinstance(event, Event)
    assert isinstance(message, Message)
    assert isinstance(skill, SkillUsage)
    assert event.semantic_outcome == Inconclusive()
    assert message.semantic_outcome == Corrected()
    assert skill.trigger_reason is TriggerReason.EXPLICIT_REQUEST


def test_annotation_job_loads_sessions_without_annotation_fields(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.ensure_directories()
    timestamp = "2026-09-19T12:00:00Z"
    legacy_session = {
        "id": "session-1",
        "model": "openai/gpt-5",
        "working_directory": "/workspace",
        "sequence": [
            {
                "timestamp": timestamp,
                "kind": "tool",
                "tool": "read",
                "event_outcome": {"tag": "Succeeded"},
            },
            {
                "timestamp": timestamp,
                "kind": "message",
                "role": "user",
                "content": "Inspect the project.",
            },
            {
                "skill": "build",
                "path": "/skills/build/SKILL.md",
                "content_hash": "abc123",
            },
        ],
    }
    session_path = settings.sessions_path.joinpath("session-1.json")
    _ = session_path.write_text(json.dumps(legacy_session), encoding="utf-8")

    async def annotate(_candidate: Session) -> SessionAnnotation:
        return make_annotation()

    report = asyncio.run(annotate_stored_sessions(settings, annotator=annotate))

    assert report == annotation_module.AnnotationReport(processed=1)
    stored = Session.model_validate_json(session_path.read_text(encoding="utf-8"))
    event, message, skill = stored.sequence
    assert isinstance(event, Event)
    assert isinstance(message, Message)
    assert isinstance(skill, SkillUsage)
    assert event.semantic_outcome == Inconclusive()
    assert message.semantic_outcome == Corrected()
    assert skill.trigger_reason is TriggerReason.EXPLICIT_REQUEST


def test_annotation_job_uses_configured_llm_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(tmp_path)
    settings.ensure_directories()
    session = make_unannotated_session()
    session_path = settings.sessions_path.joinpath("session-1.json")
    _ = session_path.write_text(session.model_dump_json(), encoding="utf-8")
    observed: list[str] = []
    agent_settings: list[Settings] = []

    class Result:
        output: SessionAnnotation = make_annotation()

    class Agent:
        async def run(self, prompt: str) -> Result:
            observed.append(prompt)
            return Result()

    def make_agent(value: Settings) -> Agent:
        agent_settings.append(value)
        return Agent()

    monkeypatch.setattr(annotation_module, "agent_from_settings", make_agent)

    report = asyncio.run(annotate_stored_sessions(settings))

    expected_prompt = (
        "Return only annotation fields for each indexed session item."
        f"\n\nSession:\n{session.model_dump_json()}"
    )
    assert report.processed == 1
    assert agent_settings == [settings]
    assert observed == [expected_prompt]
    stored = Session.model_validate_json(session_path.read_text(encoding="utf-8"))
    stored_event = stored.sequence[0]
    assert isinstance(stored_event, Event)
    assert stored_event.semantic_outcome == Inconclusive()


def test_annotation_job_preserves_session_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(tmp_path)
    settings.ensure_directories()
    session = make_unannotated_session()
    session_path = settings.sessions_path.joinpath("session-1.json")
    _ = session_path.write_text(session.model_dump_json(), encoding="utf-8")

    class Result:
        output: SessionAnnotation = make_annotation()

    class Agent:
        async def run(self, _prompt: str) -> Result:
            return Result()

    def make_agent(_settings: Settings) -> Agent:
        return Agent()

    monkeypatch.setattr(annotation_module, "agent_from_settings", make_agent)

    report = asyncio.run(annotate_stored_sessions(settings))

    assert report == annotation_module.AnnotationReport(processed=1)
    stored = Session.model_validate_json(session_path.read_text(encoding="utf-8"))
    assert stored.id == session.id
    assert stored.model == session.model
    assert stored.working_directory == session.working_directory


def test_annotation_job_skips_fully_annotated_sessions(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.ensure_directories()
    session = make_unannotated_session()
    complete = fully_annotate(session)
    _ = settings.sessions_path.joinpath("session-1.json").write_text(
        complete.model_dump_json(),
        encoding="utf-8",
    )
    calls = 0

    async def annotate(_candidate: Session) -> SessionAnnotation:
        nonlocal calls
        calls += 1
        return make_annotation()

    report = asyncio.run(annotate_stored_sessions(settings, annotator=annotate))

    assert calls == 0
    assert report.processed == 0
    assert report.skipped == 1
    assert report.failed == 0


def test_annotation_job_updates_incomplete_sessions_and_preserves_new_events(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    settings.ensure_directories()
    session = make_unannotated_session()
    session_path = settings.sessions_path.joinpath("session-1.json")
    _ = session_path.write_text(session.model_dump_json(), encoding="utf-8")
    calls: list[str] = []

    async def annotate(candidate: Session) -> SessionAnnotation:
        calls.append(candidate.id)
        new_message = Message(
            timestamp=datetime(2026, 9, 19, 12, 1, tzinfo=UTC),
            kind="message",
            role="assistant",
            semantic_outcome=None,
            content="A newer event arrived during annotation.",
        )
        latest = session.model_copy(update={"sequence": [*session.sequence, new_message]})
        _ = session_path.write_text(latest.model_dump_json(), encoding="utf-8")
        return make_annotation()

    report = asyncio.run(annotate_stored_sessions(settings, annotator=annotate))

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
    assert stored_event.semantic_outcome == Inconclusive()
    assert stored_message.semantic_outcome == Corrected()
    assert stored_skill.trigger_reason is TriggerReason.EXPLICIT_REQUEST
    assert newest_message.content == "A newer event arrived during annotation."
