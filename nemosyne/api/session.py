from datetime import datetime
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from nemosyne.model import Event, EventOutcome, Session, SkillUsage


class OmitExtra(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class CreateEvent(OmitExtra):
    timestamp: datetime
    kind: str
    tool: str
    event_outcome: EventOutcome

    def into_model(self) -> Event:
        return Event(
            timestamp=self.timestamp,
            kind=self.kind,
            tool=self.tool,
            event_outcome=self.event_outcome,
            semantic_outcome=None,
            summary=None,
        )


class CreateSkillUsage(OmitExtra):
    skill: str
    path: Path
    content_hash: str

    def into_model(self) -> SkillUsage:
        return SkillUsage(
            skill=self.skill,
            path=self.path,
            content_hash=self.content_hash,
            trigger_reason=None,
        )


CreateSequenceEvent = CreateEvent | CreateSkillUsage


class CreateSession(OmitExtra):
    id: str
    model: str
    working_directory: Path
    sequence: list[CreateSequenceEvent]

    def into_model(self) -> Session:
        return Session(
            id=self.id,
            model=self.model,
            working_directory=self.working_directory,
            sequence=[item.into_model() for item in self.sequence],
        )
