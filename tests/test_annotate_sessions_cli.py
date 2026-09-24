from pathlib import Path

import pytest

from nemosyne.cli import annotate_sessions as cli_module
from nemosyne.config.llm import Provider
from nemosyne.config.settings import Settings
from nemosyne.schedule.annotate_sessions import AnnotationReport


def test_cli_runs_session_annotation_and_prints_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        model="openai/gpt-5.6-luna",
        provider=Provider.OPENROUTER,
        skills_directory=tmp_path.joinpath("skills"),
        data_directory=tmp_path,
    )
    received: list[Settings] = []

    async def annotate(value: Settings) -> AnnotationReport:
        received.append(value)
        return AnnotationReport(processed=2, skipped=3, failed=1)

    monkeypatch.setattr(cli_module, "get_settings", lambda: settings)
    monkeypatch.setattr(cli_module, "annotate_stored_sessions", annotate)

    cli_module.main()

    assert received == [settings]
    assert capsys.readouterr().out == "processed=2 skipped=3 failed=1\n"
