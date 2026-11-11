import typer
from rich.console import Console
from rich.table import Table

from gitcoach import __version__, events, guide, shim
from gitcoach import explain as explain_module

app = typer.Typer()
guide_app = typer.Typer()
app.add_typer(guide_app, name="guide")

# 학습용 미리보기 샘플(규칙별 title·facts) — 실제 위반·이벤트 기록 없이 설명만 보여준다
_SAMPLE_VIOLATIONS: dict[str, tuple[str, dict]] = {
    "R01": (
        "보호된 브랜치(main) 직접 push",
        {"push_branch": "main", "remote": "origin"},
    ),
    "R02": ("force push", {"push_branch": "main", "remote": "origin"}),
    "R03": ("비밀 정보 staged", {"files": [".env"]}),
    "R04": ("보호된 브랜치(main) 직접 커밋", {"branch": "main"}),
    "R05": (
        "브랜치명 규칙 위반",
        {"branch_name": "MyBranch", "suggestion": "feature/cli-mybranch"},
    ),
    "R06": ("커밋 메시지 규칙 위반", {"message": "fix"}),
}


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


@app.command(name="explain")
def explain_rule(rule_id: str) -> None:
    sample = _SAMPLE_VIOLATIONS.get(rule_id.upper())
    if sample is None:
        typer.echo(
            f"알 수 없는 규칙이에요: {rule_id} (사용 가능: {', '.join(_SAMPLE_VIOLATIONS)})"
        )
        raise typer.Exit(code=1)
    title, facts = sample
    result = explain_module.explain(rule_id.upper(), title, facts)
    typer.echo(result.text)
    typer.echo(f"(llm_used={result.llm_used})")


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
