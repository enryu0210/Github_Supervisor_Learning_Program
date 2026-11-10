import typer
from rich.console import Console
from rich.table import Table

from gitcoach import __version__, events, guide, shim

app = typer.Typer()
guide_app = typer.Typer()
app.add_typer(guide_app, name="guide")


@app.callback()
def main() -> None:
    pass


@app.command()
def version() -> None:
    typer.echo(__version__)


@app.command(context_settings={"ignore_unknown_options": True})
def run(argv: list[str] = typer.Argument(None)) -> None:  # noqa: B008
    raise typer.Exit(code=shim.run(argv or []))


@guide_app.callback(invoke_without_command=True)
def guide_show(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(guide.current_prompt())


@guide_app.command()
def hint() -> None:
    typer.echo(guide.hint())


@guide_app.command()
def done() -> None:
    typer.echo(guide.done())


@guide_app.command()
def skip() -> None:
    typer.echo(guide.skip())


@guide_app.command()
def stop() -> None:
    typer.echo(guide.stop())


@app.command()
def log(today: bool = typer.Option(False, "--today")) -> None:
    rows = events.query(today=today)
    table = Table()
    for col in ("occurred_at", "rule_id", "action", "command_summary", "branch"):
        table.add_column(col)
    for e in rows:
        table.add_row(e.occurred_at, e.rule_id, e.action, e.command_summary, e.branch)
    Console().print(table)


if __name__ == "__main__":
    app()
