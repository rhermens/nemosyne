import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import ValidationError

from nemosyne.config.settings import Settings
from nemosyne.data.annotation import (
    EventAnnotation,
    MessageAnnotation,
    SequenceAnnotation,
    SessionAnnotation,
    SkillUsageAnnotation,
)
from nemosyne.data.sequence import Event, Message, Session, SkillUsage
from nemosyne.llm.annotation import annotator_from_settings

logger = logging.getLogger(__name__)
SessionAnnotator = Callable[[Session], Awaitable[SessionAnnotation]]


@dataclass(frozen=True, slots=True)
class AnnotationReport:
    processed: int = 0
    skipped: int = 0
    failed: int = 0


def session_needs_annotation(session: Session) -> bool:
    return any(
        (isinstance(item, Event) and item.semantic_outcome is None)
        or (isinstance(item, Message) and item.semantic_outcome is None)
        or (isinstance(item, SkillUsage) and item.trigger_reason is None)
        for item in session.sequence
    )


async def annotate_stored_sessions(
    settings: Settings,
    *,
    annotator: SessionAnnotator | None = None,
) -> AnnotationReport:
    settings.ensure_directories()
    paths = sorted(settings.sessions_path.glob("*.json"))
    report = AnnotationReport()

    for path in paths:
        try:
            original = _load_session(path)
        except (OSError, ValidationError):
            logger.exception("Could not load session for annotation: %s", path)
            report = replace(report, failed=report.failed + 1)
            continue

        if not session_needs_annotation(original):
            report = replace(report, skipped=report.skipped + 1)
            continue

        if annotator is None:
            annotator = annotator_from_settings(settings)

        try:
            annotation = await annotator(original)
            latest = _load_session(path)
            merged = merge_annotation(latest, original, annotation)
            _write_session(path, merged)
        except Exception:
            logger.exception("Could not annotate session: %s", path)
            report = replace(report, failed=report.failed + 1)
            continue

        report = replace(report, processed=report.processed + 1)

    logger.info(
        "Session annotation completed: processed=%d skipped=%d failed=%d",
        report.processed,
        report.skipped,
        report.failed,
    )
    return report


def merge_annotation(
    latest: Session,
    original: Session,
    annotation: SessionAnnotation,
) -> Session:
    annotations = {item.index: item for item in annotation.sequence}
    merged_sequence = [
        _merge_item(latest_item, original.sequence[index], annotations.get(index))
        if index < len(original.sequence)
        else latest_item
        for index, latest_item in enumerate(latest.sequence)
    ]
    return latest.model_copy(update={"sequence": merged_sequence})


def _merge_item(
    latest: object,
    original: object,
    annotation: SequenceAnnotation | None,
) -> object:
    if not _same_raw_item(latest, original):
        return latest

    if isinstance(latest, Event) and isinstance(annotation, EventAnnotation):
        return replace(latest, semantic_outcome=annotation.semantic_outcome)
    if isinstance(latest, Message) and isinstance(annotation, MessageAnnotation):
        return replace(latest, semantic_outcome=annotation.semantic_outcome)
    if isinstance(latest, SkillUsage) and isinstance(annotation, SkillUsageAnnotation):
        return replace(latest, trigger_reason=annotation.trigger_reason)
    return latest


def _same_raw_item(latest: object, original: object) -> bool:
    if isinstance(latest, Event) and isinstance(original, Event):
        return (
            latest.timestamp,
            latest.kind,
            latest.tool,
            latest.event_outcome,
        ) == (
            original.timestamp,
            original.kind,
            original.tool,
            original.event_outcome,
        )
    if isinstance(latest, Message) and isinstance(original, Message):
        return (
            latest.timestamp,
            latest.kind,
            latest.role,
            latest.content,
        ) == (
            original.timestamp,
            original.kind,
            original.role,
            original.content,
        )
    if isinstance(latest, SkillUsage) and isinstance(original, SkillUsage):
        return (
            latest.skill,
            latest.path,
            latest.content_hash,
        ) == (
            original.skill,
            original.path,
            original.content_hash,
        )
    return False


def _load_session(path: Path) -> Session:
    return Session.model_validate_json(path.read_text(encoding="utf-8"))


def _write_session(path: Path, session: Session) -> None:
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as file:
        _ = file.write(session.model_dump_json())
        temporary_path = Path(file.name)

    try:
        _ = temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)
