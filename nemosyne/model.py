from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from nemosyne.settings import Settings


class FailureReason(StrEnum):
    INVALID_REQUEST = "InvalidRequest"
    VALIDATION_FAILED = "ValidationFailed"
    TOOL_FAILED = "ToolFailed"
    EXTERNAL_SERVICE_FAILED = "ExternalServiceFailed"
    PERMISSION_DENIED = "PermissionDenied"
    RESOURCE_NOT_FOUND = "ResourceNotFound"
    TIMED_OUT = "TimedOut"
    CANCELLED = "Cancelled"
    INCOMPLETE_RESULT = "IncompleteResult"


class SemanticFailureReason(StrEnum):
    USER_CORRECTION = "UserCorrection"
    UNCLEAR_INSTRUCTION = "UnclearInstruction"
    UNSUPPORTED_TASK = "UnsupportedTask"


@dataclass(frozen=True, slots=True)
class Succeeded:
    tag: Literal["Succeeded"] = "Succeeded"


@dataclass(frozen=True, slots=True)
class Failed:
    reason: FailureReason
    tag: Literal["Failed"] = "Failed"


@dataclass(frozen=True, slots=True)
class Corrected:
    tag: Literal["Corrected"] = "Corrected"


@dataclass(frozen=True, slots=True)
class Inconclusive:
    tag: Literal["Inconclusive"] = "Inconclusive"


@dataclass(frozen=True, slots=True)
class SematicFailure:
    reason: SemanticFailureReason
    tag: Literal["SematicFailure"] = "SematicFailure"


EventOutcome = Succeeded | Failed | Inconclusive
SemanticOutcome = Corrected | SematicFailure | Inconclusive


@dataclass(frozen=True, slots=True)
class Event:
    timestamp: datetime
    kind: str
    tool: str
    event_outcome: EventOutcome
    semantic_outcome: SemanticOutcome | None
    summary: str | None


@dataclass(frozen=True, slots=True)
class SkillUsage:
    skill: str
    path: Path
    content_hash: str
    trigger_reason: str | None


SequenceEvent = Event | SkillUsage


@dataclass(frozen=True, slots=True)
class Session(BaseModel):
    id: str
    model: str
    working_directory: Path
    sequence: list[SequenceEvent]

    def write(self, settings: Settings) -> int:
        file_path = settings.sessions_path.joinpath(f"{self.id}.json")
        return file_path.write_text(self.model_dump_json(), "utf-8")
