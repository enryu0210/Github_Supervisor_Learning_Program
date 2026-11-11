import httpx

from gitcoach import config

TIMEOUT = 8.0
NUM_PREDICT = 200


class OllamaError(Exception):
    pass


def ask(messages: list[dict]) -> str:
    settings = config.ollama_settings()
    try:
        response = httpx.post(
            f"{settings.url}/api/chat",
            json={
                "model": settings.model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": NUM_PREDICT},
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        # "message": null이면 .get(... , {})의 기본값은 안 쓰인다(키가 존재해서) —
        # or {}로 강제해야 다음 .get("content")에서 AttributeError가 안 난다
        content = (response.json().get("message") or {}).get("content", "").strip()
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        raise OllamaError(str(exc)) from exc

    if not content:
        raise OllamaError("empty response from Ollama")
    return content
