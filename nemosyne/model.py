from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import ClassVar


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
    USER_CORRECTION = "UserCorrection"
    UNCLEAR_INSTRUCTION = "UnclearInstruction"
    UNSUPPORTED_TASK = "UnsupportedTask"


class Outcome:
    __slots__: ClassVar[tuple[str, ...]] = ()


@dataclass(frozen=True, slots=True)
class Succeeded(Outcome):
    pass


@dataclass(frozen=True, slots=True)
class Failed(Outcome):
    reason: FailureReason


@dataclass(frozen=True, slots=True)
class Corrected(Outcome):
    pass


@dataclass(frozen=True, slots=True)
class Inconclusive(Outcome):
    pass


@dataclass(frozen=True, slots=True)
class Event:
    timestamp: datetime
    kind: str
    tool: str
    outcome: Outcome
    summary: str


@dataclass(frozen=True, slots=True)
class SkillUsage:
    skill: str
    path: str
    content_hash: str
    trigger_reason: str


Sequence = Event | SkillUsage
SequenceEvent = Sequence


@dataclass(frozen=True, slots=True)
class Session:
    id: str
    model: str
    working_directory: str
    sequence: list[SequenceEvent]
