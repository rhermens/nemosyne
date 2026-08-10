from datetime import UTC, datetime

from nemosyne.model import Event, Inconclusive


def main():
    event = Event(datetime.now(UTC), "event", "", Inconclusive(), "")
    print(event)


if __name__ == "__main__":
    main()
