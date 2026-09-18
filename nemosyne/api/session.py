from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from nemosyne.config.settings import Settings
from nemosyne.data.sequence import Event, EventOutcome, Message, Session, SkillUsage


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


class CreateMessage(OmitExtra):
    timestamp: datetime
    kind: Literal["message"]
    role: Literal["user", "assistant"]
    content: str

    def into_model(self) -> Message:
        return Message(
            timestamp=self.timestamp,
            kind=self.kind,
            role=self.role,
            content=self.content,
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


CreateSequenceEvent = CreateEvent | CreateMessage | CreateSkillUsage


SessionId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]


class CreateSession(OmitExtra):
    id: SessionId
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


class StoreSessionResult(BaseModel):
    session_id: str
    stored: bool
    duplicate: bool


def save_session(data: CreateSession, settings: Settings) -> StoreSessionResult:
    """Persist the latest settled snapshot of a session."""
    settings.ensure_directories()
    session = data.into_model()
    session_path = settings.sessions_path.joinpath(f"{session.id}.json")
    serialized_session = session.model_dump_json()

    try:
        if session_path.read_text(encoding="utf-8") == serialized_session:
            return StoreSessionResult(
                session_id=session.id,
                stored=False,
                duplicate=True,
            )
    except FileNotFoundError:
        pass

    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=session_path.parent,
        prefix=f".{session_path.name}.",
        delete=False,
    ) as file:
        _ = file.write(serialized_session)
        temporary_path = Path(file.name)

    try:
        _ = temporary_path.replace(session_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return StoreSessionResult(
        session_id=session.id,
        stored=True,
        duplicate=False,
    )
