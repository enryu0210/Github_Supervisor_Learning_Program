import typer

from gitcoach import __version__

app = typer.Typer()


@app.callback()
def main() -> None:
    pass


@app.command()
def version() -> None:
    typer.echo(__version__)


if __name__ == "__main__":
    app()
