from nemosyne.config.settings import get_settings
from nemosyne.llm.agent import dbg_agent_from_settings


def main() -> None:
    settings = get_settings()
    settings.ensure_directories()

    agent = dbg_agent_from_settings(settings)
    print(agent.run_sync("Hi"))


if __name__ == "__main__":
    main()
