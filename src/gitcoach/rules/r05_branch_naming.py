import re

from gitcoach.models import Command, Context, Violation

_AREAS = ("cli", "watcher", "web", "db", "infra")
_AREA_PATTERN = "|".join(_AREAS)
_FEATURE_FIX_RE = re.compile(rf"^(feature|fix)/({_AREA_PATTERN})-[a-z0-9-]+$")
_DOCS_RE = re.compile(r"^docs/[a-z0-9-]+$")
_RELEASE_RE = re.compile(r"^release/v\d+\.\d+$")

_CREATE_FLAGS = {"-b", "-B", "-c", "-C"}
_BRANCH_SKIP_FLAGS = {"-d", "-D", "-m", "-M", "-a", "-r", "-v", "--list"}

_CONSEQUENCE = "watcher가 다시 경고하고, pr-convention 검사가 실패하고, 대시보드 통계에서 빠질 수 있어요."


def is_valid_branch_name(name: str) -> bool:
    return bool(
        _FEATURE_FIX_RE.match(name) or _DOCS_RE.match(name) or _RELEASE_RE.match(name)
    )


def _clean(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "change"


def _extract_area(remainder: str) -> tuple[str, str]:
    lowered = remainder.lower()
    for area in _AREAS:
        if lowered == area:
            return area, ""
        for sep in ("-", "_"):
            token = area + sep
            if lowered.startswith(token):
                return area, remainder[len(token) :]
    return "cli", remainder


def suggest_name(name: str) -> str:
    prefix, sep, rest = name.partition("/")
    prefix_lower = prefix.lower()
    remainder = rest if sep else name

    if sep and prefix_lower == "release":
        version = remainder.strip()
        if re.fullmatch(r"v\d+\.\d+", version):
            return f"release/{version}"
        return "release/v0.1"

    if sep and prefix_lower == "docs":
        return f"docs/{_clean(remainder)}"

    base_prefix = (
        prefix_lower if sep and prefix_lower in ("feature", "fix") else "feature"
    )
    area, desc_source = _extract_area(remainder)
    return f"{base_prefix}/{area}-{_clean(desc_source)}"


def _creating_branch_name(cmd: Command) -> str | None:
    if cmd.subcommand in ("checkout", "switch"):
        if not (_CREATE_FLAGS & set(cmd.flags)):
            return None
        # `checkout -b <새 이름> [시작점]`: 마지막 인자는 시작점일 수 있어 첫 인자를 본다
        return cmd.positionals[0] if cmd.positionals else None
    if cmd.subcommand == "branch":
        if _BRANCH_SKIP_FLAGS & set(cmd.flags):
            return None
        return cmd.positionals[0] if len(cmd.positionals) == 1 else None
    return None


def check_branch_naming(cmd: Command, ctx: Context) -> Violation | None:
    name = _creating_branch_name(cmd)
    if name is None or is_valid_branch_name(name):
        return None

    suggestion = suggest_name(name)
    return Violation(
        rule_id="R05",
        title="브랜치명 규칙 위반",
        severity="low",
        facts={"branch_name": name, "suggestion": suggestion},
        guide_id="r05_branch_naming",
        allow_run=True,
        warning=f"브랜치 이름 '{name}'이 규칙에 안 맞아요. 제안: {suggestion}",
        consequence=_CONSEQUENCE,
    )
