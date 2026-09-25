from collections.abc import Awaitable, Callable, Mapping
from itertools import batched

from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    ChoiceAnswer,
)

from nemosyne.config.auth import AuthStorage
from nemosyne.config.llm import Provider
from nemosyne.config.settings import Settings
from nemosyne.data.annotation import (
    EventAnnotation,
    MessageAnnotation,
    SequenceAnnotation,
    SessionAnnotation,
    SkillUsageAnnotation,
)
from nemosyne.data.sequence import (
    Corrected,
    Event,
    Inconclusive,
    Message,
    SemanticFailureReason,
    SemanticOutcome,
    SematicFailure,
    Session,
    TriggerReason,
)

SessionAnnotator = Callable[[Session], Awaitable[SessionAnnotation]]
MAX_QUESTIONS_PER_REQUEST = 64


def annotator_from_settings(settings: Settings) -> SessionAnnotator:
    api_key = AuthStorage.load(settings.auth_path)[Provider.TYPESAFE]

    async def annotate(session: Session) -> SessionAnnotation:
        async with AsyncTypeSafeClient(api_key=api_key.value) as client:
            return await annotate_session(session, client)

    return annotate


def annotation_questions(session: Session) -> Mapping[str, Choice]:
    questions: dict[str, Choice] = {}
    for index, item in enumerate(session.sequence):
        if isinstance(item, Event | Message):
            if item.semantic_outcome is not None:
                continue
            questions[f"semantic_outcome_{index}"] = Choice(
                instructions=(
                    f"What is the semantic outcome of sequence[{index}]?"
                ),
                criteria={
                    "Corrected": "Successfully corrects an earlier mistake.",
                    "UserCorrection": "The user identifies or corrects a mistake.",
                    "UnclearInstruction": "The instruction is too ambiguous to follow.",
                    "UnsupportedTask": "The requested task cannot be performed.",
                    "Inconclusive": "No other semantic outcome is supported.",
                },
            )
        else:
            if item.trigger_reason is not None:
                continue
            questions[f"trigger_reason_{index}"] = Choice(
                instructions=f"Why was the skill in sequence[{index}] used?",
                criteria={
                    TriggerReason.EXPLICIT_REQUEST.value: (
                        "The user explicitly requested the skill or named capability."
                    ),
                    TriggerReason.TASK_MATCH.value: (
                        "The task matched the skill's documented purpose."
                    ),
                    TriggerReason.PROJECT_REQUIREMENT.value: (
                        "Project instructions required the skill."
                    ),
                    TriggerReason.AGENT_DECISION.value: (
                        "The agent selected the skill without another listed trigger."
                    ),
                    TriggerReason.UNKNOWN.value: (
                        "The available session evidence does not establish why."
                    ),
                },
            )
    return questions


async def annotate_session(
    session: Session,
    client: AsyncTypeSafeClient,
) -> SessionAnnotation:
    state = session.model_dump(mode="json")
    choices: dict[str, ChoiceAnswer] = {}
    question_items = annotation_questions(session).items()
    for question_batch in batched(question_items, MAX_QUESTIONS_PER_REQUEST):
        result = await client.system_one(  # pyright: ignore[reportUnknownMemberType]
            state=state,
            questions=dict(question_batch),
        )
        choices.update(result.choices)
    return annotation_from_choices(session, choices)


def annotation_from_choices(
    session: Session,
    choices: Mapping[str, ChoiceAnswer],
) -> SessionAnnotation:
    annotations: list[SequenceAnnotation] = []
    for index, item in enumerate(session.sequence):
        if isinstance(item, Event):
            if item.semantic_outcome is not None:
                continue
            annotations.append(
                EventAnnotation(
                    index=index,
                    semantic_outcome=_semantic_outcome(
                        choices[f"semantic_outcome_{index}"].choice
                    ),
                )
            )
        elif isinstance(item, Message):
            if item.semantic_outcome is not None:
                continue
            annotations.append(
                MessageAnnotation(
                    index=index,
                    semantic_outcome=_semantic_outcome(
                        choices[f"semantic_outcome_{index}"].choice
                    ),
                )
            )
        else:
            if item.trigger_reason is not None:
                continue
            annotations.append(
                SkillUsageAnnotation(
                    index=index,
                    trigger_reason=TriggerReason(
                        choices[f"trigger_reason_{index}"].choice
                    ),
                )
            )
    return SessionAnnotation(sequence=annotations)


def _semantic_outcome(choice: str) -> SemanticOutcome:
    if choice == "Corrected":
        return Corrected()
    if choice == "Inconclusive":
        return Inconclusive()
    return SematicFailure(reason=SemanticFailureReason(choice))
