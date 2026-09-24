import asyncio

from nemosyne.config.settings import get_settings
from nemosyne.schedule.annotate_sessions import annotate_stored_sessions


def main() -> None:
    report = asyncio.run(annotate_stored_sessions(get_settings()))
    print(f"processed={report.processed} skipped={report.skipped} failed={report.failed}")


if __name__ == "__main__":
    main()
