import shutil

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
