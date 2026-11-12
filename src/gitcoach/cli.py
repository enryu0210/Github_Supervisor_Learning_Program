import os

import typer
from rich.console import Console
from rich.table import Table

from gitcoach import __version__, config, events, guide, shim, wrapper
from gitcoach import doctor as doctor_module
from gitcoach import explain as explain_module
from gitcoach import sync as sync_module

app = typer.Typer()
guide_app = typer.Typer()
app.add_typer(guide_app, name="guide")
config_app = typer.Typer()
app.add_typer(config_app, name="config")

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


@config_app.callback(invoke_without_command=True)
def config_show(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    typer.echo(f"protected = {config.protected_branches()}")
    typer.echo(f"disabled_rules = {sorted(config.disabled_rules())}")
    settings = config.ollama_settings()
    typer.echo(f"ollama.url = {settings.url}")
    typer.echo(f"ollama.model = {settings.model}")
    _warn_if_ollama_url_overridden()


@config_app.command("protected")
def config_protected(branches: list[str] = typer.Argument(None)) -> None:  # noqa: B008
    if not branches:
        typer.echo(", ".join(config.protected_branches()))
        return
    try:
        config.set_protected_branches(branches)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(f"보호 브랜치를 설정했어요: {', '.join(branches)}")


@config_app.command("disable-rule")
def config_disable_rule(rule_id: str) -> None:
    try:
        config.disable_rule(rule_id.upper())
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(f"{rule_id.upper()}을 껐어요")


@config_app.command("enable-rule")
def config_enable_rule(rule_id: str) -> None:
    try:
        config.enable_rule(rule_id.upper())
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(f"{rule_id.upper()}을 켰어요")


@config_app.command("ollama")
def config_ollama(
    url: str = typer.Option(None, "--url"),
    model: str = typer.Option(None, "--model"),
) -> None:
    if url is None and model is None:
        settings = config.ollama_settings()
        typer.echo(f"url = {settings.url}")
        typer.echo(f"model = {settings.model}")
        _warn_if_ollama_url_overridden()
        return
    try:
        config.set_ollama_settings(url=url, model=model)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo("Ollama 설정을 저장했어요")
    _warn_if_ollama_url_overridden()


def _warn_if_ollama_url_overridden() -> None:
    if os.environ.get("OLLAMA_URL"):
        typer.echo(
            "참고: 환경변수 OLLAMA_URL이 우선 적용돼 이 값은 무시돼요 "
            f"(현재 OLLAMA_URL={os.environ['OLLAMA_URL']})"
        )


@app.command()
def log(today: bool = typer.Option(False, "--today")) -> None:
    rows = events.query(today=today)
    table = Table()
    for col in ("occurred_at", "rule_id", "action", "command_summary", "branch"):
        table.add_column(col)
    for e in rows:
        table.add_row(e.occurred_at, e.rule_id, e.action, e.command_summary, e.branch)
    Console().print(table)


@app.command()
def sync() -> None:
    try:
        result = sync_module.push_events()
    except sync_module.SyncError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"전송 완료: 새로 저장 {result.inserted}건, 중복(이미 저장됨) {result.duplicate}건"
    )
    if result.rejected:
        typer.echo(f"거절됨 {len(result.rejected)}건:")
        for event_id, reason in result.rejected:
            typer.echo(f"  {event_id}: {reason}")


@app.command()
def init() -> None:
    installed = wrapper.install()
    typer.echo("쉘 래퍼를 설치했어요:")
    for item in installed:
        typer.echo(f"  - {item}")

    login = config.member()
    if login is not None:
        typer.echo(f"이미 설정된 member: {login}")
    else:
        login = config.detect_github_login()
        if login is None:
            typer.echo("gh로 GitHub 아이디를 확인하지 못했어요")
            login = typer.prompt("GitHub 아이디를 입력해 주세요").strip().lower()
        config.set_member(login)
        typer.echo(f"설정을 저장했어요: member = {login}")

    # Ollama는 꺼져 있어도 init 자체는 실패하지 않음(완료 기준 "Ollama 꺼도 동작") — 정보 제공용
    ok, message = doctor_module.check_ollama()
    typer.echo(("✅ " if ok else "⚠️ ") + message)


@app.command()
def doctor() -> None:
    exit_code = 0

    git_ok, git_message = doctor_module.check_git()
    typer.echo(("✅ " if git_ok else "❌ ") + git_message)
    if not git_ok:
        exit_code = 1

    ollama_ok, ollama_message = doctor_module.check_ollama()
    typer.echo(("✅ " if ollama_ok else "⚠️ ") + ollama_message)

    wrapper_status = doctor_module.check_wrapper()
    for label, installed in wrapper_status.items():
        prefix = "✅ " if installed else "⚠️ "
        typer.echo(f"{prefix}쉘 래퍼({label}): {'설치됨' if installed else '미설치'}")
    if not any(wrapper_status.values()):
        typer.echo("❌ 설치된 쉘 래퍼가 없어요 — gitcoach init을 실행해 주세요")
        exit_code = 1

    raise typer.Exit(code=exit_code)


@app.command()
def uninstall() -> None:
    removed = wrapper.uninstall()
    if not removed:
        typer.echo("제거할 쉘 래퍼가 없어요")
        return
    typer.echo("쉘 래퍼를 제거했어요:")
    for item in removed:
        typer.echo(f"  - {item}")


if __name__ == "__main__":
    app()
