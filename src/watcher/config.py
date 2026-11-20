import os
import re
from dataclasses import dataclass
from pathlib import Path

TOKEN_ENV = "GITHUB_TOKEN"
REPO_ENV = "GITHUB_REPO"
POLL_INTERVAL_ENV = "WATCHER_POLL_INTERVAL_SECONDS"
EVENTS_DIR_ENV = "WATCHER_EVENTS_DIR"
PRS_PATH_ENV = "WATCHER_PRS_PATH"

DEFAULT_POLL_INTERVAL_SECONDS = 300
DEFAULT_EVENTS_DIR = "./events"
DEFAULT_PRS_PATH = "./prs.json"

_REPO_PATTERN = re.compile(r"^[^/\s]+/[^/\s]+$")


class WatcherConfigError(Exception):
    pass


@dataclass
class WatcherConfig:
    token: str
    repo: str
    poll_interval_seconds: int
    events_dir: Path
    prs_path: Path


def load_config() -> WatcherConfig:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise WatcherConfigError(f"환경변수 {TOKEN_ENV}이 필요해요.")

    repo = os.environ.get(REPO_ENV)
    if not repo:
        raise WatcherConfigError(f"환경변수 {REPO_ENV}(owner/name 형식)이 필요해요.")
    repo = repo.strip().lower()
    if not _REPO_PATTERN.match(repo):
        raise WatcherConfigError(
            f"환경변수 {REPO_ENV}는 owner/name 형식이어야 해요: {repo!r}"
        )

    poll_interval_seconds = _poll_interval()
    events_dir = Path(os.environ.get(EVENTS_DIR_ENV) or DEFAULT_EVENTS_DIR)
    prs_path = Path(os.environ.get(PRS_PATH_ENV) or DEFAULT_PRS_PATH)

    return WatcherConfig(
        token=token,
        repo=repo,
        poll_interval_seconds=poll_interval_seconds,
        events_dir=events_dir,
        prs_path=prs_path,
    )


def _poll_interval() -> int:
    raw = os.environ.get(POLL_INTERVAL_ENV)
    if not raw:
        return DEFAULT_POLL_INTERVAL_SECONDS
    try:
        value = int(raw)
    except ValueError as exc:
        raise WatcherConfigError(
            f"환경변수 {POLL_INTERVAL_ENV}는 정수여야 해요: {raw!r}"
        ) from exc
    if value <= 0:
        raise WatcherConfigError(
            f"환경변수 {POLL_INTERVAL_ENV}는 0보다 커야 해요: {value}"
        )
    return value
