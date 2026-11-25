import httpx

from watcher.config import WatcherConfig

BASE_URL = "https://api.github.com"
TIMEOUT = 10.0

# 모듈 전역으로 재사용 — 매 호출마다 TCP+TLS를 새로 맺으면 PR당 리뷰 조회처럼
# 한 틱에 수십~백여 회 연속 호출될 때 타임아웃이 잦아진다(keep-alive로 완화).
_client = httpx.Client()


class GitHubClientError(Exception):
    pass


def _get_url(config: WatcherConfig, url: str) -> httpx.Response:
    try:
        response = _client.get(
            url,
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


def get(config: WatcherConfig, path: str) -> httpx.Response:
    return _get_url(config, f"{BASE_URL}{path}")


def _paginate(config: WatcherConfig, path: str) -> list[dict]:
    """목록 엔드포인트의 `Link` 헤더(`rel="next"`)를 따라가며 모든 페이지를
    합친다. 한 페이지(최대 100건)만 읽으면 그 이상인 레포에서 PR·리뷰가
    조용히 누락된다(watcher-load.md 4절은 전체 페이지 적재를 전제한다)."""
    response = get(config, path)
    results = list(_json(response))
    next_url = response.links.get("next", {}).get("url")
    while next_url:
        response = _get_url(config, next_url)
        results.extend(_json(response))
        next_url = response.links.get("next", {}).get("url")
    return results


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
    return _paginate(
        config,
        f"/repos/{config.repo}/pulls?state=open&sort=updated&direction=desc&per_page=100",
    )


def list_all_pulls(config: WatcherConfig) -> list[dict]:
    return _paginate(
        config,
        f"/repos/{config.repo}/pulls?state=all&sort=updated&direction=desc&per_page=100",
    )


def list_pull_commits(config: WatcherConfig, number: int) -> list[dict]:
    return _json(get(config, f"/repos/{config.repo}/pulls/{number}/commits"))


def list_pull_reviews(config: WatcherConfig, number: int) -> list[dict]:
    return _json(get(config, f"/repos/{config.repo}/pulls/{number}/reviews"))
