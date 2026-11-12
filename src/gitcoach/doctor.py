import shutil
import sys
from pathlib import Path

import httpx

from gitcoach import config, wrapper

TIMEOUT = 3.0


def check_git() -> tuple[bool, str]:
    path = shutil.which("git")
    if path is None:
        return False, "git을 찾을 수 없어요"
    return True, f"git 설치됨 ({path})"


def check_ollama() -> tuple[bool, str]:
    settings = config.ollama_settings()
    try:
        response = httpx.get(f"{settings.url}/api/tags", timeout=TIMEOUT)
        response.raise_for_status()
        models = [m.get("name", "") for m in response.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return False, f"Ollama에 연결할 수 없어요 ({settings.url})"
    if settings.model in models:
        return True, f"Ollama 연결됨, 모델 {settings.model} 확인됨"
    shown = ", ".join(models) if models else "없음"
    return (
        False,
        f"Ollama는 연결되지만 모델 {settings.model}을 찾을 수 없어요 (설치된 모델: {shown})",
    )


def check_wrapper() -> dict[str, bool]:
    return wrapper.status()


def check_global_install() -> tuple[bool, str]:
    """gitcoach가 프로젝트 .venv 안에만 설치됐는지 확인한다. pip install -e .로 설치하면
    .venv를 수동 활성화해야 git 래퍼가 동작하므로, 터미널을 새로 열 때마다 코칭이
    빠지는 문제가 생긴다. pipx install -e .로 설치하면 이 검사를 통과한다."""
    if ".venv" in Path(sys.executable).parts:
        message = (
            "venv 안에 설치되어 있어요 — 터미널마다 활성화가 필요해요 "
            "(pipx install -e . 로 다시 설치하면 항상 켜져 있어요)"
        )
        return False, message
    return True, "전역 설치 확인됨 — 터미널을 새로 열어도 바로 동작해요"
