from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from nemosyne.api.session import CreateSequenceEvent, CreateSession, SessionId
from nemosyne.config.settings import Settings, get_settings


class StoreSessionResult(BaseModel):
    session_id: str
    stored: bool
    duplicate: bool


class SessionIdConflict(ValueError):
    pass


def save_session(data: CreateSession, settings: Settings) -> StoreSessionResult:
    """Persist a session once and reject reuse of its ID for different data."""
    settings.ensure_directories()
    session = data.into_model()
    session_path = settings.sessions_path.joinpath(f"{session.id}.json")

    serialized_session = session.model_dump_json()
    try:
        with session_path.open("x", encoding="utf-8") as file:
            _ = file.write(serialized_session)
    except FileExistsError:
        if session_path.read_text(encoding="utf-8") != serialized_session:
            raise SessionIdConflict(
                f"Session ID {session.id!r} already contains different data"
            ) from None
        return StoreSessionResult(
            session_id=session.id,
            stored=False,
            duplicate=True,
        )

    return StoreSessionResult(
        session_id=session.id,
        stored=True,
        duplicate=False,
    )


def store_session(
    id: SessionId,
    model: str,
    working_directory: Path,
    sequence: list[CreateSequenceEvent],
) -> StoreSessionResult:
    """Store a completed agent session for later pattern analysis and skill curation."""
    return save_session(
        CreateSession(
            id=id,
            model=model,
            working_directory=working_directory,
            sequence=sequence,
        ),
        get_settings(),
    )


def register_session_tools(mcp: FastMCP):
    mcp.add_tool(store_session, structured_output=True)
