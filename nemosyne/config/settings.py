from functools import cache
from pathlib import Path
from typing import ClassVar, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from apscheduler.triggers.cron import (  # pyright: ignore[reportMissingTypeStubs]
    CronTrigger,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator

from nemosyne.config.llm import Provider


class SchedulerSettings(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    enabled: bool = False
    cron: str = "0 3 * * *"
    timezone: str = "UTC"

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        try:
            _ = CronTrigger.from_crontab(value)  # pyright: ignore[reportUnknownMemberType]
        except ValueError as error:
            raise ValueError("invalid cron expression") from error
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            _ = ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("unknown scheduler timezone") from error
        return value


class Settings(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    model: str
    provider: Provider
    skills_directory: Path
    data_directory: Path
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)

    @property
    def auth_path(self) -> Path:
        return self.data_directory.expanduser().joinpath("auth.json")

    @property
    def sessions_path(self) -> Path:
        return self.data_directory.expanduser().joinpath("sessions")

    def ensure_directories(self) -> None:
        return self.sessions_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, *paths: Path) -> Self:
        for path in paths:
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as file:
                return cls.model_validate(yaml.safe_load(file))
        raise NoSettings()


class NoSettings(BaseException):
    pass


@cache
def get_settings() -> Settings:
    return Settings.load(Path("./settings.yaml"), Path("~/.nemosyne/settings.yaml"))
