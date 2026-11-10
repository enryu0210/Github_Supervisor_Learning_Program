import os

import httpx

MODEL = "gemma4:e2b"
TIMEOUT = 8.0
NUM_PREDICT = 200


class OllamaError(Exception):
    pass


def ask(messages: list[dict]) -> str:
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    try:
        response = httpx.post(
            f"{base_url}/api/chat",
            json={
                "model": MODEL,
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
