import json
from pathlib import Path

CACHE_PATH = Path.home() / ".gitcoach" / "explain_cache.json"


def make_key(rule_id: str, facts: dict) -> str:
    return f"{rule_id}\x1f{json.dumps(facts, sort_keys=True, ensure_ascii=False)}"


def _load() -> dict:
    """캐시 파일이 없거나 깨져 있으면(JSON 파싱 실패·인코딩 오류·읽기 권한 없음)
    빈 캐시로 취급한다. 캐시는 있으면 좋은 것일 뿐 가이드 시작을 막아선 안 된다."""
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def get(key: str) -> str | None:
    return _load().get(key)


def set(key: str, text: str) -> None:
    data = _load()
    data[key] = text
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
