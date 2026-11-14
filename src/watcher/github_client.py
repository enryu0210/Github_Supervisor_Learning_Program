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


def get_repo(config: WatcherConfig) -> dict:
    return get(config, f"/repos/{config.repo}").json()
