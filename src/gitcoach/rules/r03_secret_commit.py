from gitcoach.models import Command, Context, Violation

_WARNING = "비밀 정보가 담긴 파일이 staged 상태예요."
_CONSEQUENCE = "허용 불가 — 그대로 커밋하면 기록에 영구히 남아요."

_CHECKED_SUBCOMMANDS = {"add", "commit", "push"}
_KEY_FILENAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
_KEY_EXTENSIONS = (".pem", ".key", ".pfx", ".p12")


def _is_secret_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    if name in _KEY_FILENAMES:
        return True
    return name.endswith(_KEY_EXTENSIONS)


def check_secret_commit(cmd: Command, ctx: Context) -> Violation | None:
    if cmd.subcommand not in _CHECKED_SUBCOMMANDS:
        return None

    matched = [f for f in ctx.staged_files if _is_secret_file(f)]
    if not matched:
        return None

    return Violation(
        rule_id="R03",
        title="비밀 정보 staged",
        severity="high",
        facts={"files": matched},
        guide_id="r03_secret_commit",
        allow_run=False,
        warning=_WARNING,
        consequence=_CONSEQUENCE,
    )
