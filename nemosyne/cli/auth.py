from argparse import ArgumentParser
from typing import cast

import questionary

from nemosyne.config.auth import ApiKey, AuthStorage
from nemosyne.config.llm import Provider
from nemosyne.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    settings.ensure_directories()
    parser = ArgumentParser()
    _ = parser.add_argument(
        "provider",
        choices=list(Provider),
        default=settings.provider,
        nargs="?",
        type=Provider,
    )
    provider = cast(Provider, parser.parse_args().provider)

    auth = AuthStorage.load(settings.auth_path)
    api_key = cast(str, questionary.password(f"Enter {provider.value} API key: ").ask())
    if api_key == "":
        return

    auth.root[provider] = ApiKey(api_key)
    _ = auth.store(settings.auth_path)


if __name__ == "__main__":
    main()
