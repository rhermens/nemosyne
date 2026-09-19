import asyncio
import logging
from pathlib import Path
from typing import Protocol, cast

import pytest
from apscheduler.schedulers.asyncio import (  # pyright: ignore[reportMissingTypeStubs]
    AsyncIOScheduler,
)
from fastapi.testclient import TestClient
from pydantic import ValidationError

from nemosyne.cli.daemon import create_app
from nemosyne.config.llm import Provider
from nemosyne.config.settings import SchedulerSettings, Settings
from nemosyne.scheduler import create_scheduler, scheduled_maintenance


class ConfiguredJob(Protocol):
    trigger: object
    coalesce: bool
    max_instances: int


def test_scheduler_is_disabled_by_default() -> None:
    assert create_scheduler(SchedulerSettings()) is None


def test_scheduler_registers_maintenance_cron_job() -> None:
    scheduler = create_scheduler(
        SchedulerSettings(enabled=True, cron="15 3 * * *", timezone="Europe/Amsterdam")
    )

    assert isinstance(scheduler, AsyncIOScheduler)
    job = cast(
        ConfiguredJob | None,
        scheduler.get_job("scheduled-maintenance"),  # pyright: ignore[reportUnknownMemberType]
    )
    assert job is not None
    assert str(job.trigger) == "cron[month='*', day='*', day_of_week='*', hour='3', minute='15']"
    assert str(scheduler.timezone) == "Europe/Amsterdam"
    assert job.coalesce is True
    assert job.max_instances == 1


def test_scheduler_rejects_invalid_cron_expression() -> None:
    with pytest.raises(ValidationError, match="cron expression"):
        _ = SchedulerSettings(enabled=True, cron="not a cron expression")


def test_scheduler_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        _ = SchedulerSettings(enabled=True, timezone="Mars/Olympus")


def test_scheduler_starts_and_stops_apscheduler() -> None:
    scheduler = create_scheduler(SchedulerSettings(enabled=True))
    assert isinstance(scheduler, AsyncIOScheduler)

    async def run_lifecycle() -> None:
        scheduler.start()
        assert scheduler.running
        scheduler.shutdown(wait=False)
        await asyncio.sleep(0)
        assert not scheduler.running

    asyncio.run(run_lifecycle())


def test_daemon_starts_and_stops_enabled_scheduler(tmp_path: Path) -> None:
    settings = Settings(
        model="openai/gpt-5.6-luna",
        provider=Provider.OPENROUTER,
        skills_directory=tmp_path.joinpath("skills"),
        data_directory=tmp_path,
        scheduler=SchedulerSettings(enabled=True),
    )

    class FakeScheduler:
        def __init__(self) -> None:
            self.started: bool = False
            self.stopped: bool = False

        def start(self) -> None:
            self.started = True

        def shutdown(self, wait: bool = True) -> None:
            assert wait is False
            self.stopped = True

    scheduler = FakeScheduler()
    app = create_app(
        settings_loader=lambda: settings,
        scheduler_factory=lambda _settings: scheduler,
    )

    with TestClient(app):
        assert scheduler.started
    assert scheduler.stopped


def test_scheduled_maintenance_is_observable(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        scheduled_maintenance()

    assert "Scheduled maintenance completed" in caplog.messages
