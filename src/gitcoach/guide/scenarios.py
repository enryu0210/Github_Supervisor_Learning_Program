import re

from gitcoach.models import Command, Context, GuideStep, Scenario, ViolationSnapshot

_AREA = "cli|watcher|web|db|infra|docs"
_BRANCH_RE = re.compile(rf"^(feature|fix)/({_AREA})-[a-z0-9-]+$")


def _is_valid_branch_name(name: str) -> bool:
    return bool(_BRANCH_RE.match(name))


def _r01_step1(cmd: Command, ctx: Context, snap: ViolationSnapshot) -> bool:
    if cmd.subcommand not in ("switch", "checkout"):
        return False
    if not ({"-c", "-b"} & set(cmd.flags)):
        return False
    if not cmd.positionals:
        return False
    return _is_valid_branch_name(cmd.positionals[-1])


def _r01_step2(cmd: Command, ctx: Context, snap: ViolationSnapshot) -> bool:
    if cmd.subcommand != "push":
        return False
    if not ({"-u", "--set-upstream"} & set(cmd.flags)):
        return False
    if cmd.remote != "origin":
        return False
    return cmd.refspec is None or cmd.refspec == ctx.current_branch


_R01 = Scenario(
    guide_id="r01_protected_push",
    title="feature 브랜치로 옮겨 PR 올리기",
    summary="main에는 직접 push하지 않고, feature 브랜치로 옮겨 PR로 올린다",
    steps=[
        GuideStep(
            instruction="지금 커밋을 가진 새 브랜치를 만드세요.",
            hint="git switch -c feature/<영역>-<설명> 형식으로 만드세요",
            answer="git switch -c feature/cli-login-fix",
            expect=_r01_step1,
        ),
        GuideStep(
            instruction="새 브랜치를 내 fork(origin)에 올리세요.",
            hint="git push -u origin <브랜치>",
            answer="git push -u origin feature/cli-login-fix",
            expect=_r01_step2,
        ),
        GuideStep(
            instruction="upstream develop을 base로 PR을 올리세요.",
            hint="gh pr create --base develop",
            answer="gh pr create --base develop",
            expect=None,
        ),
    ],
)


def _r02_step1(cmd: Command, ctx: Context, snap: ViolationSnapshot) -> bool:
    if cmd.subcommand == "pull":
        return "--rebase" in cmd.flags
    if cmd.subcommand == "rebase":
        return "--continue" in cmd.flags
    return False


def _r02_step2(cmd: Command, ctx: Context, snap: ViolationSnapshot) -> bool:
    return cmd.subcommand == "push"


_R02 = Scenario(
    guide_id="r02_force_push",
    title="원격 변경을 가져와 안전하게 push",
    summary="force push 대신 pull --rebase로 맞추고 일반 push로 올린다",
    steps=[
        GuideStep(
            instruction="원격의 최신 변경을 먼저 가져오세요.",
            hint="git pull --rebase (충돌 시 해결 후 git rebase --continue)",
            answer="git pull --rebase",
            expect=_r02_step1,
        ),
        GuideStep(
            instruction="이제 안전하게 push하세요.",
            hint="git push",
            answer="git push",
            expect=_r02_step2,
        ),
    ],
)


def _r03_step1(cmd: Command, ctx: Context, snap: ViolationSnapshot) -> bool:
    if cmd.subcommand not in ("restore", "reset"):
        return False
    if "--staged" not in cmd.flags:
        return False
    flagged = set(snap.facts.get("files", []))
    return bool(flagged) and flagged.issubset(set(cmd.positionals))


def _r03_step3(cmd: Command, ctx: Context, snap: ViolationSnapshot) -> bool:
    return cmd.subcommand == "add" and ".gitignore" in cmd.positionals


_R03 = Scenario(
    guide_id="r03_secret_commit",
    title="비밀 파일 빼고 .gitignore에 등록",
    summary="비밀 파일은 스테이징에서 빼고 .gitignore로 다시 못 올라가게 막는다",
    steps=[
        GuideStep(
            instruction="스테이징에서 비밀 파일을 빼세요.",
            hint="git restore --staged <파일>",
            answer="git restore --staged .env",
            expect=_r03_step1,
        ),
        GuideStep(
            instruction=".gitignore에 비밀 파일 패턴을 추가하세요.",
            hint=".gitignore 파일을 열어 추가하세요 (예: .env)",
            answer="echo '.env' >> .gitignore",
            expect=None,
        ),
        GuideStep(
            instruction=".gitignore를 커밋에 포함하세요.",
            hint="git add .gitignore",
            answer="git add .gitignore",
            expect=_r03_step3,
        ),
    ],
)


SCENARIOS: dict[str, Scenario] = {
    _R01.guide_id: _R01,
    _R02.guide_id: _R02,
    _R03.guide_id: _R03,
}
