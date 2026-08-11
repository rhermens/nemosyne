from datetime import UTC, datetime
from pathlib import Path

from nemosyne.model import Event, Inconclusive, Session, Succeeded
from nemosyne.settings import get_settings


def main() -> None:
    settings = get_settings()
    settings.ensure_directories()

    session = Session(
        id="test-session",
        model=settings.model,
        working_directory=Path.cwd(),
        sequence=[
            Event(
                timestamp=datetime.now(UTC),
                kind="authentication",
                tool="auth",
                event_outcome=Succeeded(),
                semantic_outcome=Inconclusive(),
                summary="Authentication session initialized",
            )
        ],
    )

    print(session.write(settings))


if __name__ == "__main__":
    main()
