import logging
from dataclasses import dataclass
from typing import final
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import (  # pyright: ignore[reportMissingTypeStubs]
    AsyncIOScheduler,
)
from apscheduler.triggers.cron import (  # pyright: ignore[reportMissingTypeStubs]
    CronTrigger,
)

from nemosyne.config.settings import SchedulerSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScheduledJobInfo:
    id: str
    trigger: str
    timezone: str
    coalesce: bool
    max_instances: int


@final
class DaemonScheduler:
    def __init__(
        self,
        backend: AsyncIOScheduler,
        jobs: tuple[ScheduledJobInfo, ...],
    ) -> None:
        self._backend = backend
        self._jobs = {job.id: job for job in jobs}
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def get_job_info(self, job_id: str) -> ScheduledJobInfo | None:
        return self._jobs.get(job_id)

    def start(self) -> None:
        if self._running:
            return
        self._backend.start()
        self._running = True

    async def shutdown(self) -> None:
        if not self._running:
            return
        self._backend.shutdown(wait=False)
        self._running = False


def scheduled_maintenance() -> None:
    """Run the observable placeholder for future maintenance work."""
    logger.info("Scheduled maintenance completed")


def create_scheduler(settings: SchedulerSettings) -> DaemonScheduler | None:
    """Build the daemon scheduler without starting it."""
    if not settings.enabled:
        return None

    timezone = ZoneInfo(settings.timezone)
    trigger = CronTrigger.from_crontab(  # pyright: ignore[reportUnknownMemberType]
        settings.cron,
        timezone=timezone,
    )
    backend = AsyncIOScheduler(timezone=timezone)
    _ = backend.add_job(  # pyright: ignore[reportUnknownMemberType]
        scheduled_maintenance,
        trigger,
        id="scheduled-maintenance",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    info = ScheduledJobInfo(
        id="scheduled-maintenance",
        trigger=str(trigger),
        timezone=str(timezone),
        coalesce=True,
        max_instances=1,
    )
    return DaemonScheduler(backend=backend, jobs=(info,))
