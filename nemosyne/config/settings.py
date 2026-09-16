from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel

from nemosyne.config.llm import Provider


@dataclass(frozen=True, slots=True)
class Settings(BaseModel):
    model: str
    provider: Provider
    skills_directory: Path
    data_directory: Path

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
