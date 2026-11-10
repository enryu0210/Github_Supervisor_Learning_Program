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
    except httpx.HTTPError as exc:
        raise OllamaError(str(exc)) from exc

    content = response.json().get("message", {}).get("content", "").strip()
    if not content:
        raise OllamaError("empty response from Ollama")
    return content
