from typer.testing import CliRunner

from gitcoach import __version__
from gitcoach.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_run_command(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("gitcoach.shim.run", lambda argv: calls.append(argv) or 0)
    result = runner.invoke(app, ["run", "--", "status"])
    assert result.exit_code == 0
    assert calls == [["status"]]
