import httpx

from watcher.config import WatcherConfig

TIMEOUT = 5.0


def check(config: WatcherConfig) -> tuple[bool, str]:
    """Ollama 연결만 확인한다 — watcher는 아직 Ollama를 쓰지 않으므로(퀴즈
    생성은 별도 PR) 실패해도 호출부가 기동을 막지 않도록 예외 대신 결과를
    돌려준다."""
    try:
        response = httpx.get(f"{config.ollama_url}/api/tags", timeout=TIMEOUT)
        response.raise_for_status()
        models = [m.get("name", "") for m in response.json().get("models", [])]
        # join 도 try 안에 둔다 — name 이 문자열이 아닌 응답이면 TypeError 가 난다.
        shown = ", ".join(models) if models else "없음"
    # 응답 모양이 예상과 다르면(models 항목이 dict 가 아님 등) AttributeError/TypeError 가
    # 난다. 헬스체크는 기동을 막지 않아야 하므로 이것도 실패 결과로 돌려준다.
    except (httpx.HTTPError, ValueError, AttributeError, TypeError):
        return False, f"Ollama에 연결할 수 없어요 ({config.ollama_url})"

    return True, f"Ollama 연결됨 ({config.ollama_url}), 설치된 모델: {shown}"
