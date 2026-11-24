import httpx

from gitcoach import config

TIMEOUT = 8.0
NUM_PREDICT = 200


class OllamaError(Exception):
    pass


def ask(
    messages: list[dict],
    *,
    url: str | None = None,
    model: str | None = None,
    num_predict: int = NUM_PREDICT,
    timeout: float = TIMEOUT,
) -> str:
    settings = config.ollama_settings()
    resolved_url = url or settings.url
    resolved_model = model or settings.model
    try:
        response = httpx.post(
            f"{resolved_url}/api/chat",
            json={
                "model": resolved_model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": num_predict},
            },
            timeout=timeout,
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
