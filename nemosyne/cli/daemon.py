import uvicorn
from fastapi import FastAPI

from nemosyne.api.session import CreateSession
from nemosyne.model import Session
from nemosyne.settings import SettingsDependency

app = FastAPI(title="Nemosyne daemon")


@app.post("/sessions")
async def accept_session(data: CreateSession, settings: SettingsDependency) -> Session:
    session = data.into_model()
    _ = session.write(settings)
    return session


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
