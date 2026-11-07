from typer.testing import CliRunner

from gitcoach import __version__
from gitcoach.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
