import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import (  # pyright: ignore[reportMissingTypeStubs]
    AsyncIOScheduler,
)
from apscheduler.triggers.cron import (  # pyright: ignore[reportMissingTypeStubs]
    CronTrigger,
)

from nemosyne.config.settings import SchedulerSettings

logger = logging.getLogger(__name__)


def scheduled_maintenance() -> None:
    """Run the observable placeholder for future maintenance work."""
    logger.info("Scheduled maintenance completed")


def create_scheduler(settings: SchedulerSettings) -> AsyncIOScheduler | None:
    """Build the daemon scheduler without starting it."""
    if not settings.enabled:
        return None

    timezone = ZoneInfo(settings.timezone)
    trigger = CronTrigger.from_crontab(  # pyright: ignore[reportUnknownMemberType]
        settings.cron,
        timezone=timezone,
    )
    scheduler = AsyncIOScheduler(timezone=timezone)
    _ = scheduler.add_job(  # pyright: ignore[reportUnknownMemberType]
        scheduled_maintenance,
        trigger,
        id="scheduled-maintenance",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
