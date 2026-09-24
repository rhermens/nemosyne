from collections.abc import Callable

from pydantic_ai import Agent, models, providers
from pydantic_ai.providers.openrouter import OpenRouterProvider

from nemosyne.config.auth import ApiKey, AuthStorage
from nemosyne.config.llm import Provider
from nemosyne.config.settings import Settings
from nemosyne.data.annotation import SessionAnnotation


class ProviderNotImplemented(BaseException):
    pass


def provider_factory_with_key(api_key: ApiKey) -> Callable[[str], providers.Provider]:
    def make(provider: str):
        match provider:
            case Provider.OPENROUTER:
                return OpenRouterProvider(api_key=api_key.value)
            case _:
                raise ProviderNotImplemented("Not implemented")

    return make


def agent_from_settings(settings: Settings) -> Agent[None, SessionAnnotation]:
    auth = AuthStorage.load(settings.auth_path)
    api_key = auth[settings.provider]

    model = models.infer_model(
        f"{settings.provider}:{settings.model}", provider_factory_with_key(api_key)
    )
    return Agent(
        model,
        instructions=(
            "Return one annotation item for every indexed session item. "
            "For each Event, return only its index and semantic_outcome. "
            "For each Message, return only its index and semantic_outcome. "
            "For each SkillUsage, return only its index and trigger_reason."
        ),
        output_type=SessionAnnotation,
    )


def dbg_agent_from_settings(settings: Settings) -> Agent:
    auth = AuthStorage.load(settings.auth_path)
    api_key = auth[settings.provider]

    model = models.infer_model(
        f"{settings.provider}:{settings.model}", provider_factory_with_key(api_key)
    )
    return Agent(
        model,
    )
