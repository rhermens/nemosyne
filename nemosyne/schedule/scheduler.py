from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import (  # pyright: ignore[reportMissingTypeStubs]
    AsyncIOScheduler,
)
from apscheduler.triggers.cron import (  # pyright: ignore[reportMissingTypeStubs]
    CronTrigger,
)

from nemosyne.config.settings import Settings
from nemosyne.schedule.annotate_sessions import annotate_stored_sessions


def create_scheduler(settings: Settings) -> AsyncIOScheduler | None:
    """Build the daemon scheduler without starting it."""
    if not settings.scheduler.enabled:
        return None

    timezone = ZoneInfo(settings.scheduler.timezone)
    trigger = CronTrigger.from_crontab(  # pyright: ignore[reportUnknownMemberType]
        settings.scheduler.cron,
        timezone=timezone,
    )
    scheduler = AsyncIOScheduler(timezone=timezone)
    _ = scheduler.add_job(  # pyright: ignore[reportUnknownMemberType]
        annotate_stored_sessions,
        trigger,
        args=(settings,),
        id="annotate-sessions",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
