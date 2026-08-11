from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import Depends
from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class Settings(BaseModel):
    model: str
    provider: str
    skills_directory: Path
    data_directory: Path

    @property
    def sessions_path(self) -> Path:
        return self.data_directory.expanduser().joinpath("sessions")

    def ensure_directories(self) -> None:
        return self.sessions_path.mkdir(parents=True, exist_ok=True)


class NoSettings(BaseException):
    pass


@cache
def get_settings() -> Settings:
    local_json = Path("./settings.yaml")
    if local_json.exists():
        with local_json.open(encoding="utf-8") as file:
            return Settings.model_validate(yaml.safe_load(file))

    json = Path("~/.nemosyne/settings.yaml").expanduser()
    if not json.exists():
        raise NoSettings()

    with json.open(encoding="utf-8") as file:
        return Settings.model_validate(yaml.safe_load(file))


SettingsDependency = Annotated[Settings, Depends(get_settings)]
