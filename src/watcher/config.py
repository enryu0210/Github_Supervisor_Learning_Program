import os
import re
from dataclasses import dataclass
from pathlib import Path

TOKEN_ENV = "GITHUB_TOKEN"
REPO_ENV = "GITHUB_REPO"
POLL_INTERVAL_ENV = "WATCHER_POLL_INTERVAL_SECONDS"
REVIEW_CONCENTRATION_PATH_ENV = "WATCHER_REVIEW_CONCENTRATION_PATH"
SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_SERVICE_KEY_ENV = "SUPABASE_SERVICE_KEY"
OLLAMA_URL_ENV = "OLLAMA_URL"
OLLAMA_MODEL_ENV = "OLLAMA_MODEL"
QUIZ_BATCH_SIZE_ENV = "WATCHER_QUIZ_BATCH_SIZE"

DEFAULT_POLL_INTERVAL_SECONDS = 300
DEFAULT_REVIEW_CONCENTRATION_PATH = "./review_concentration.json"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "gemma4:e2b"
DEFAULT_QUIZ_BATCH_SIZE = 10

_REPO_PATTERN = re.compile(r"^[^/\s]+/[^/\s]+$")


class WatcherConfigError(Exception):
    pass


@dataclass
class WatcherConfig:
    token: str
    repo: str
    poll_interval_seconds: int
    review_concentration_path: Path
    supabase_url: str
    supabase_service_key: str
    ollama_url: str = DEFAULT_OLLAMA_URL
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    quiz_batch_size: int = DEFAULT_QUIZ_BATCH_SIZE


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

    supabase_url = os.environ.get(SUPABASE_URL_ENV)
    if not supabase_url:
        raise WatcherConfigError(f"환경변수 {SUPABASE_URL_ENV}이 필요해요.")

    supabase_service_key = os.environ.get(SUPABASE_SERVICE_KEY_ENV)
    if not supabase_service_key:
        raise WatcherConfigError(f"환경변수 {SUPABASE_SERVICE_KEY_ENV}이 필요해요.")

    poll_interval_seconds = _poll_interval()
    review_concentration_path = Path(
        os.environ.get(REVIEW_CONCENTRATION_PATH_ENV)
        or DEFAULT_REVIEW_CONCENTRATION_PATH
    )
    ollama_url = os.environ.get(OLLAMA_URL_ENV) or DEFAULT_OLLAMA_URL
    ollama_model = os.environ.get(OLLAMA_MODEL_ENV) or DEFAULT_OLLAMA_MODEL
    quiz_batch_size = _quiz_batch_size()

    return WatcherConfig(
        token=token,
        repo=repo,
        poll_interval_seconds=poll_interval_seconds,
        review_concentration_path=review_concentration_path,
        supabase_url=supabase_url,
        supabase_service_key=supabase_service_key,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        quiz_batch_size=quiz_batch_size,
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


def _quiz_batch_size() -> int:
    raw = os.environ.get(QUIZ_BATCH_SIZE_ENV)
    if not raw:
        return DEFAULT_QUIZ_BATCH_SIZE
    try:
        value = int(raw)
    except ValueError as exc:
        raise WatcherConfigError(
            f"환경변수 {QUIZ_BATCH_SIZE_ENV}는 정수여야 해요: {raw!r}"
        ) from exc
    if value <= 0:
        raise WatcherConfigError(
            f"환경변수 {QUIZ_BATCH_SIZE_ENV}는 0보다 커야 해요: {value}"
        )
    return value
