import os
import subprocess
import tomllib
from pathlib import Path

from gitcoach.models import OllamaSettings

GLOBAL_CONFIG_PATH = Path.home() / ".gitcoach" / "config.toml"

# "repo_root 인자를 안 줬다"(직접 구해야 함)와 "None이라 레포가 아니다"(확정)를
# 구분하기 위한 sentinel. None 자체를 기본값으로 쓰면 둘이 같은 값이 되어 버린다.
_UNRESOLVED = object()

_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_OLLAMA_MODEL = "gemma4:e2b"


def find_repo_root() -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def _repo_config_path(repo_root: Path | None) -> Path | None:
    if repo_root is None:
        return None
    return repo_root / ".gitcoach.toml"


def _resolve(repo_root: Path | None) -> Path | None:
    if repo_root is _UNRESOLVED:
        repo_root = find_repo_root()
    return _repo_config_path(repo_root)


def _load_toml(path: Path | None, *, strict: bool = False) -> dict:
    """설정 파일이 없거나 깨져 있으면(TOML 문법 오류·인코딩 오류·읽기 권한 없음)
    빈 설정으로 취급한다. 설정은 있으면 좋은 것일 뿐 CLI 동작을 막아선 안 된다.

    단, 쓰기 경로(`strict=True`)는 예외다: 깨진 파일을 빈 설정으로 취급하면
    read-modify-write가 그 빈 dict로 기존 내용을 덮어써 버리므로, 여기서는
    에러를 내서 쓰기를 멈춘다."""
    if path is None or not path.exists():
        return {}
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, ValueError) as exc:
        if strict:
            raise ValueError(f"설정 파일을 읽을 수 없어요: {path} ({exc})") from exc
        return {}


def _as_str_list(value: object, default: list[str]) -> list[str]:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    return default


def _as_str(value: object, default: str | None) -> str | None:
    if isinstance(value, str):
        return value
    return default


def _dump_toml(data: dict) -> str:
    """이 모듈이 실제로 쓰는 값 형태(문자열·문자열 리스트·1단계 테이블)만 지원하는
    직접 구현. 범용 TOML 쓰기가 필요 없어 외부 라이브러리를 추가하지 않는다."""
    lines = []
    tables = {}
    for key, value in data.items():
        if isinstance(value, dict):
            tables[key] = value
            continue
        lines.append(f"{key} = {_dump_value(value)}")
    for table_name, table in tables.items():
        lines.append(f"\n[{table_name}]")
        for key, value in table.items():
            lines.append(f"{key} = {_dump_value(value)}")
    return "\n".join(lines) + "\n"


def _dump_value(value: object) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_dump_string(v) for v in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _dump_string(value)
    raise TypeError(f"unsupported TOML value: {value!r}")


def _dump_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def _write_toml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_toml(data), encoding="utf-8")


def protected_branches(repo_root: Path | None = _UNRESOLVED) -> list[str]:
    data = _load_toml(_resolve(repo_root))
    return _as_str_list(data.get("protected"), ["main"])


def set_protected_branches(
    branches: list[str], *, repo_root: Path | None = _UNRESOLVED
) -> None:
    if repo_root is _UNRESOLVED:
        repo_root = find_repo_root()
    path = _repo_config_path(repo_root)
    if path is None:
        raise ValueError("레포 밖에서는 보호 브랜치를 설정할 수 없어요")
    data = _load_toml(path, strict=True)
    data["protected"] = branches
    _write_toml(path, data)


def disabled_rules(repo_root: Path | None = _UNRESOLVED) -> set[str]:
    data = _load_toml(_resolve(repo_root))
    rules = {r.upper() for r in _as_str_list(data.get("disabled_rules"), [])}
    rules.discard("R03")  # R03은 레포 공용 설정으로도 끌 수 없음(read-time 강제)
    return rules


def disable_rule(rule_id: str, *, repo_root: Path | None = _UNRESOLVED) -> None:
    if rule_id == "R03":
        raise ValueError("R03은 끌 수 없어요")
    if repo_root is _UNRESOLVED:
        repo_root = find_repo_root()
    path = _repo_config_path(repo_root)
    if path is None:
        raise ValueError("레포 밖에서는 규칙을 설정할 수 없어요")
    data = _load_toml(path, strict=True)
    rules = {r.upper() for r in _as_str_list(data.get("disabled_rules"), [])}
    rules.add(rule_id)
    data["disabled_rules"] = sorted(rules)
    _write_toml(path, data)


def enable_rule(rule_id: str, *, repo_root: Path | None = _UNRESOLVED) -> None:
    if repo_root is _UNRESOLVED:
        repo_root = find_repo_root()
    path = _repo_config_path(repo_root)
    if path is None:
        raise ValueError("레포 밖에서는 규칙을 설정할 수 없어요")
    data = _load_toml(path, strict=True)
    rules = {r.upper() for r in _as_str_list(data.get("disabled_rules"), [])}
    rules.discard(rule_id)
    data["disabled_rules"] = sorted(rules)
    _write_toml(path, data)


def member() -> str | None:
    data = _load_toml(GLOBAL_CONFIG_PATH)
    return _as_str(data.get("member"), None)


def ollama_settings() -> OllamaSettings:
    data = _load_toml(GLOBAL_CONFIG_PATH)
    ollama = data.get("ollama")
    ollama = ollama if isinstance(ollama, dict) else {}

    url = os.environ.get("OLLAMA_URL") or _as_str(
        ollama.get("url"), _DEFAULT_OLLAMA_URL
    )
    model = _as_str(ollama.get("model"), _DEFAULT_OLLAMA_MODEL)
    return OllamaSettings(url=url, model=model)


def set_ollama_settings(*, url: str | None = None, model: str | None = None) -> None:
    if url is None and model is None:
        return
    data = _load_toml(GLOBAL_CONFIG_PATH, strict=True)
    ollama = data.get("ollama")
    ollama = dict(ollama) if isinstance(ollama, dict) else {}
    if url is not None:
        ollama["url"] = url
    if model is not None:
        ollama["model"] = model
    data["ollama"] = ollama
    _write_toml(GLOBAL_CONFIG_PATH, data)
