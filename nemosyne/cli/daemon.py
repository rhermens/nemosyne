from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI

from nemosyne.api.session import CreateSession, StoreSessionResult, save_session
from nemosyne.config.settings import Settings, get_settings

app = FastAPI(title="Nemosyne daemon")


@app.post("/sessions")
def store_session(
    data: CreateSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> StoreSessionResult:
    """Store the latest settled session snapshot for later skill curation."""
    return save_session(data, settings)


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=9787)


if __name__ == "__main__":
    main()
