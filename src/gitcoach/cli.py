import typer

from gitcoach import __version__, guide, shim

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


if __name__ == "__main__":
    app()
