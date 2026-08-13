from typing import cast

import questionary

from nemosyne.config.auth import ApiKey, AuthStorage
from nemosyne.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    settings.ensure_directories()

    auth = AuthStorage.load(settings.auth_path)
    api_key = cast(str, questionary.password("Enter API key: ").ask())
    if api_key == "":
        return

    auth.root[settings.provider] = ApiKey(api_key)
    _ = auth.store(settings.auth_path)


if __name__ == "__main__":
    main()
