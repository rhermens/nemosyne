from pathlib import Path
from typing import cast

from pydantic_ai.models import Model

from nemosyne.config.auth import ApiKey, AuthStorage
from nemosyne.config.llm import Provider
from nemosyne.config.settings import Settings
from nemosyne.llm.agent import dbg_agent_from_settings


def test_debug_agent_uses_configured_openrouter_model(tmp_path: Path) -> None:
    settings = Settings(
        model="openai/gpt-5.6-luna",
        provider=Provider.OPENROUTER,
        skills_directory=tmp_path.joinpath("skills"),
        data_directory=tmp_path,
    )
    _ = AuthStorage(
        root={Provider.OPENROUTER: ApiKey("test-api-key")}
    ).store(settings.auth_path)

    agent = dbg_agent_from_settings(settings)
    model = cast(Model, agent.model)

    assert model.system == "openrouter"
    assert model.model_name == "openai/gpt-5.6-luna"
