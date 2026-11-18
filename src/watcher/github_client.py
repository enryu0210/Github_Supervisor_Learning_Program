import httpx

from watcher.config import WatcherConfig

BASE_URL = "https://api.github.com"
TIMEOUT = 10.0


class GitHubClientError(Exception):
    pass


def get(config: WatcherConfig, path: str) -> httpx.Response:
    try:
        response = httpx.get(
            f"{BASE_URL}{path}",
            headers={
                "Authorization": f"Bearer {config.token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except (httpx.HTTPError, ValueError) as exc:
        raise GitHubClientError(f"GitHub API 호출에 실패했어요: {exc}") from exc
    return response


def _json(response: httpx.Response) -> dict | list:
    try:
        return response.json()
    except ValueError as exc:
        raise GitHubClientError(
            f"GitHub API 응답을 JSON으로 해석할 수 없어요: {exc}"
        ) from exc


def get_repo(config: WatcherConfig) -> dict:
    return _json(get(config, f"/repos/{config.repo}"))


def list_events(config: WatcherConfig) -> list[dict]:
    return _json(get(config, f"/repos/{config.repo}/events"))


def compare_commits(config: WatcherConfig, base: str, head: str) -> dict:
    return _json(get(config, f"/repos/{config.repo}/compare/{base}...{head}"))


def list_pulls_for_commit(config: WatcherConfig, sha: str) -> list[dict]:
    return _json(get(config, f"/repos/{config.repo}/commits/{sha}/pulls"))


def list_branches(config: WatcherConfig) -> list[dict]:
    return _json(get(config, f"/repos/{config.repo}/branches"))


def get_commit(config: WatcherConfig, sha: str) -> dict:
    return _json(get(config, f"/repos/{config.repo}/commits/{sha}"))


def list_open_pulls(config: WatcherConfig) -> list[dict]:
    return _json(get(config, f"/repos/{config.repo}/pulls?state=open"))
