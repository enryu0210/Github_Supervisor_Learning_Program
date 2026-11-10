import json
from pathlib import Path

CACHE_PATH = Path.home() / ".gitcoach" / "explain_cache.json"


def make_key(rule_id: str, facts: dict) -> str:
    return f"{rule_id}\x1f{json.dumps(facts, sort_keys=True, ensure_ascii=False)}"


def get(key: str) -> str | None:
    if not CACHE_PATH.exists():
        return None
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return data.get(key)


def set(key: str, text: str) -> None:
    data = {}
    if CACHE_PATH.exists():
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    data[key] = text
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
