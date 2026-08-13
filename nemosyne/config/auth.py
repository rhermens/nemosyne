from dataclasses import dataclass
from pathlib import Path
from typing import Self

from pydantic import RootModel

from nemosyne.model.llm import Provider


@dataclass(frozen=True)
class ApiKey:
    value: str


class AuthStorage(RootModel[dict[Provider, ApiKey]]):
    @classmethod
    def load(cls, path: Path) -> Self:
        if not path.exists():
            return cls(root={})
        return cls.model_validate_json(path.read_text("utf-8"))

    def store(self, path: Path) -> int:
        return path.write_text(self.model_dump_json(), encoding="utf-8")

    def __setitem__(self, provider: Provider, key: ApiKey) -> None:
        self.root[provider] = key

    def __getitem__(self, provider: Provider) -> ApiKey:
        return self.root[provider]
