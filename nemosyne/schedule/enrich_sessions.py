import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import ValidationError

from nemosyne.config.settings import Settings
from nemosyne.data.sequence import Event, Message, Session, SkillUsage
from nemosyne.llm.agent import agent_from_settings

logger = logging.getLogger(__name__)
SessionEnricher = Callable[[Session], Awaitable[Session]]


@dataclass(frozen=True, slots=True)
class EnrichmentReport:
    processed: int = 0
    skipped: int = 0
    failed: int = 0


def session_needs_enrichment(session: Session) -> bool:
    return any(
        (isinstance(item, Event) and (item.summary is None or item.semantic_outcome is None))
        or (isinstance(item, Message) and item.semantic_outcome is None)
        or (isinstance(item, SkillUsage) and item.trigger_reason is None)
        for item in session.sequence
    )


async def enrich_stored_sessions(
    settings: Settings,
    *,
    enrich: SessionEnricher | None = None,
) -> EnrichmentReport:
    settings.ensure_directories()
    paths = sorted(settings.sessions_path.glob("*.json"))
    enricher = enrich
    report = EnrichmentReport()

    for path in paths:
        try:
            original = _load_session(path)
        except (OSError, ValidationError):
            logger.exception("Could not load session for enrichment: %s", path)
            report = replace(report, failed=report.failed + 1)
            continue

        if not session_needs_enrichment(original):
            report = replace(report, skipped=report.skipped + 1)
            continue

        if enricher is None:
            enricher = _configured_enricher(settings)

        try:
            enriched = await enricher(original)
            if enriched.id != original.id:
                raise ValueError("enriched session ID does not match source session")
            latest = _load_session(path)
            merged = merge_enrichment(latest, original, enriched)
            _write_session(path, merged)
        except Exception:
            logger.exception("Could not enrich session: %s", path)
            report = replace(report, failed=report.failed + 1)
            continue

        report = replace(report, processed=report.processed + 1)

    logger.info(
        "Session enrichment completed: processed=%d skipped=%d failed=%d",
        report.processed,
        report.skipped,
        report.failed,
    )
    return report


def merge_enrichment(latest: Session, original: Session, enriched: Session) -> Session:
    merged_sequence = [
        _merge_item(latest_item, original.sequence[index], enriched.sequence[index])
        if index < len(original.sequence) and index < len(enriched.sequence)
        else latest_item
        for index, latest_item in enumerate(latest.sequence)
    ]
    return latest.model_copy(update={"sequence": merged_sequence})


def _merge_item(latest: object, original: object, enriched: object) -> object:
    if type(latest) is not type(original) or type(original) is not type(enriched):
        return latest
    if not _same_raw_item(latest, original):
        return latest

    if isinstance(latest, Event) and isinstance(enriched, Event):
        return replace(
            latest,
            semantic_outcome=enriched.semantic_outcome,
            summary=enriched.summary,
        )
    if isinstance(latest, Message) and isinstance(enriched, Message):
        return replace(latest, semantic_outcome=enriched.semantic_outcome)
    if isinstance(latest, SkillUsage) and isinstance(enriched, SkillUsage):
        return replace(latest, trigger_reason=enriched.trigger_reason)
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


def _configured_enricher(settings: Settings) -> SessionEnricher:
    agent = agent_from_settings(settings)

    async def enrich(session: Session) -> Session:
        result = await agent.run(
            "Add summaries and semantic outcomes to this session without changing raw events.",
            deps=session,
        )
        return result.output

    return enrich


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
