import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Self, cast

import httpx2
import pytest
from typesafe_sdk import AsyncTypeSafeClient, Choice, ChoiceAnswer

from nemosyne.config.auth import ApiKey, AuthStorage
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
    SemanticFailureReason,
    SematicFailure,
    Session,
    SkillUsage,
    Succeeded,
    TriggerReason,
)
from nemosyne.llm import annotation as jev_annotation


def make_session() -> Session:
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
            ),
            Message(
                timestamp=timestamp,
                kind="message",
                role="user",
                content="Inspect the project.",
            ),
            SkillUsage(
                skill="build",
                path=Path("/skills/build/SKILL.md"),
                content_hash="abc123",
            ),
        ],
    )


def answer(choice: str) -> ChoiceAnswer:
    return ChoiceAnswer(choice=choice, confidence=1.0, probabilities={choice: 1.0})


def question_payload(question: Choice) -> dict[str, object]:
    return cast(dict[str, object], question.model_dump())


def test_annotator_from_settings_loads_typesafe_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        model="openai/gpt-5",
        provider=Provider.OPENROUTER,
        skills_directory=tmp_path.joinpath("skills"),
        data_directory=tmp_path,
    )
    _ = AuthStorage(
        root={
            Provider.OPENROUTER: ApiKey("openrouter-key"),
            Provider.TYPESAFE: ApiKey("typesafe-key"),
        }
    ).store(settings.auth_path)
    observed_keys: list[str] = []

    class Response:
        choices: ClassVar[dict[str, ChoiceAnswer]] = {
            "semantic_outcome_0": answer("Inconclusive"),
            "semantic_outcome_1": answer("Corrected"),
            "trigger_reason_2": answer("ExplicitRequest"),
        }

    class Client:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        async def system_one(self, **_kwargs: object) -> Response:
            return Response()

    def make_client(*, api_key: str) -> Client:
        observed_keys.append(api_key)
        return Client()

    monkeypatch.setattr(jev_annotation, "AsyncTypeSafeClient", make_client)

    annotation = asyncio.run(jev_annotation.annotator_from_settings(settings)(make_session()))

    assert annotation.sequence == make_annotation_sequence()
    assert observed_keys == ["typesafe-key"]


def test_annotation_questions_skip_items_with_existing_annotations() -> None:
    session = make_session()
    event = session.sequence[0]
    assert isinstance(event, Event)
    partially_annotated = session.model_copy(
        update={
            "sequence": [
                replace(event, semantic_outcome=Inconclusive()),
                *session.sequence[1:],
            ]
        }
    )

    questions = jev_annotation.annotation_questions(partially_annotated)

    assert "semantic_outcome_0" not in questions


def test_annotation_questions_uses_typed_choices_for_each_session_item() -> None:
    questions = jev_annotation.annotation_questions(make_session())

    assert set(questions) == {
        "semantic_outcome_0",
        "semantic_outcome_1",
        "trigger_reason_2",
    }
    semantic_question = question_payload(questions["semantic_outcome_0"])
    trigger_question = question_payload(questions["trigger_reason_2"])
    assert "sequence[0]" in cast(str, semantic_question["instructions"])
    assert "sequence[2]" in cast(str, trigger_question["instructions"])
    assert set(cast(dict[str, object], semantic_question["criteria"])) == {
        "Corrected",
        "UserCorrection",
        "UnclearInstruction",
        "UnsupportedTask",
        "Inconclusive",
    }
    assert set(cast(dict[str, object], trigger_question["criteria"])) == {
        reason.value for reason in TriggerReason
    }


def test_annotate_session_sends_state_and_typed_questions_to_jev() -> None:
    observed: list[dict[str, object]] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        observed.append(cast(dict[str, object], json.loads(request.content)))
        return httpx2.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "semantic_outcome_0": {
                        "type": "choice",
                        "choice": "Inconclusive",
                        "confidence": 1.0,
                        "probabilities": {"Inconclusive": 1.0},
                    },
                    "semantic_outcome_1": {
                        "type": "choice",
                        "choice": "Corrected",
                        "confidence": 1.0,
                        "probabilities": {"Corrected": 1.0},
                    },
                    "trigger_reason_2": {
                        "type": "choice",
                        "choice": "ExplicitRequest",
                        "confidence": 1.0,
                        "probabilities": {"ExplicitRequest": 1.0},
                    },
                },
                "usage": {"input_tokens": 10, "output_tokens": 3},
            },
        )

    async def run() -> SessionAnnotation:
        async with AsyncTypeSafeClient(
            api_key="test-key",
            transport=httpx2.MockTransport(handle),
        ) as client:
            return await jev_annotation.annotate_session(make_session(), client)

    annotation = asyncio.run(run())

    assert annotation.sequence == make_annotation_sequence()
    assert observed[0]["state"] == make_session().model_dump(mode="json")
    assert set(cast(dict[str, object], observed[0]["questions"])) == {
        "semantic_outcome_0",
        "semantic_outcome_1",
        "trigger_reason_2",
    }


def make_annotation_sequence() -> list[
    EventAnnotation | MessageAnnotation | SkillUsageAnnotation
]:
    return [
        EventAnnotation(index=0, semantic_outcome=Inconclusive()),
        MessageAnnotation(index=1, semantic_outcome=Corrected()),
        SkillUsageAnnotation(
            index=2,
            trigger_reason=TriggerReason.EXPLICIT_REQUEST,
        ),
    ]


def test_annotation_from_jev_choices_preserves_existing_annotations() -> None:
    session = make_session()
    event = session.sequence[0]
    assert isinstance(event, Event)
    partially_annotated = session.model_copy(
        update={
            "sequence": [
                replace(event, semantic_outcome=Inconclusive()),
                *session.sequence[1:],
            ]
        }
    )

    annotation = jev_annotation.annotation_from_choices(
        partially_annotated,
        {
            "semantic_outcome_1": answer("Corrected"),
            "trigger_reason_2": answer("ExplicitRequest"),
        },
    )

    assert annotation == SessionAnnotation(
        sequence=[
            MessageAnnotation(index=1, semantic_outcome=Corrected()),
            SkillUsageAnnotation(
                index=2,
                trigger_reason=TriggerReason.EXPLICIT_REQUEST,
            ),
        ]
    )


def test_annotation_from_jev_choices_maps_semantic_failures() -> None:
    session = make_session().model_copy(update={"sequence": make_session().sequence[:1]})

    annotation = jev_annotation.annotation_from_choices(
        session,
        {"semantic_outcome_0": answer("UserCorrection")},
    )

    assert annotation == SessionAnnotation(
        sequence=[
            EventAnnotation(
                index=0,
                semantic_outcome=SematicFailure(
                    reason=SemanticFailureReason.USER_CORRECTION
                ),
            )
        ]
    )


def test_annotation_from_jev_choices_maps_session_items() -> None:
    annotation = jev_annotation.annotation_from_choices(
        make_session(),
        {
            "semantic_outcome_0": answer("Inconclusive"),
            "semantic_outcome_1": answer("Corrected"),
            "trigger_reason_2": answer("ExplicitRequest"),
        },
    )

    assert annotation == SessionAnnotation(sequence=make_annotation_sequence())
