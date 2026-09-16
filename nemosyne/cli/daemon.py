import uvicorn
from fastapi import FastAPI

from nemosyne.api.session import CreateSession
from nemosyne.config.settings import SettingsDependency
from nemosyne.data.sequence import Session
from nemosyne.signals.sequence import SequenceCreated

app = FastAPI(title="Nemosyne daemon")


@app.post("/sessions")
async def accept_session(
    data: CreateSession, settings: SettingsDependency, sequence_created: SequenceCreated
) -> Session:
    session = data.into_model()
    _ = session.write(settings)
    _ = sequence_created.send("sequences", session_id=session.id)
    return session


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
