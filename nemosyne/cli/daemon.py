from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Protocol

import uvicorn
from fastapi import Depends, FastAPI

from nemosyne.api.session import CreateSession, StoreSessionResult, save_session
from nemosyne.config.settings import SchedulerSettings, Settings, get_settings
from nemosyne.schedule.scheduler import create_scheduler


class RunningScheduler(Protocol):
    def start(self) -> None:
        """Start scheduled job processing."""

    def shutdown(self, wait: bool = True) -> None:
        """Stop scheduled job processing."""


SchedulerFactory = Callable[[SchedulerSettings], RunningScheduler | None]
SettingsLoader = Callable[[], Settings]


def create_app(
    settings_loader: SettingsLoader = get_settings,
    scheduler_factory: SchedulerFactory = create_scheduler,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        scheduler = scheduler_factory(settings_loader().scheduler)
        if scheduler is not None:
            scheduler.start()
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)

    application = FastAPI(title="Nemosyne daemon", lifespan=lifespan)

    def store_session(
        data: CreateSession,
        settings: Annotated[Settings, Depends(settings_loader)],
    ) -> StoreSessionResult:
        """Store the latest settled session snapshot for later skill curation."""
        return save_session(data, settings)

    application.add_api_route(
        "/sessions",
        store_session,
        methods=["POST"],
        response_model=StoreSessionResult,
    )
    return application


app = create_app()


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=9787)


if __name__ == "__main__":
    main()
