from collections.abc import Callable

from pydantic_ai import Agent, models, providers
from pydantic_ai.providers.openrouter import OpenRouterProvider

from nemosyne.config.auth import ApiKey, AuthStorage
from nemosyne.config.llm import Provider
from nemosyne.config.settings import Settings
from nemosyne.data.sequence import Session


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


def agent_from_settings(settings: Settings) -> Agent[Session, Session]:
    auth = AuthStorage.load(settings.auth_path)
    api_key = auth[settings.provider]

    model = models.infer_model(settings.model, provider_factory_with_key(api_key))
    return Agent(
        model,
        instructions="Given an LLM Session with conversational sequence events and skill usages, you are to determine and fill the semantic_outcome and summary for events, and the trigger reason for skill usages",
        deps_type=Session,
        output_type=Session,
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
