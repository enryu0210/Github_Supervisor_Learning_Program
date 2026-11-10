import json

import httpx

from gitcoach import explain as explain_module
from gitcoach.explain import cache, ollama, templates


class _FakeResponse:
    def __init__(self, content: str, status_code: int = 200) -> None:
        self._content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def json(self) -> dict:
        return {"message": {"content": self._content}}


class _NonJsonResponse(_FakeResponse):
    """프록시 오류 페이지처럼 200인데 본문이 JSON이 아닌 경우."""

    def __init__(self) -> None:
        super().__init__("")

    def json(self):
        raise json.JSONDecodeError("Expecting value", "<html>...</html>", 0)


class _NullMessageResponse(_FakeResponse):
    """`message` 키는 있지만 값이 null인 경우 — dict.get의 default는 안 쓰인다."""

    def __init__(self) -> None:
        super().__init__("")

    def json(self) -> dict:
        return {"message": None}


def _use_tmp_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cache, "CACHE_PATH", tmp_path / "explain_cache.json")


def test_ollama_ask_returns_content_on_success(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse("설명입니다."))
    assert ollama.ask([{"role": "user", "content": "hi"}]) == "설명입니다."


def test_ollama_ask_raises_on_timeout(monkeypatch) -> None:
    def raise_timeout(*a, **k):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", raise_timeout)
    try:
        ollama.ask([{"role": "user", "content": "hi"}])
        assert False, "OllamaError를 기대했지만 예외가 발생하지 않았어요"
    except ollama.OllamaError:
        pass


def test_ollama_ask_raises_on_connect_error(monkeypatch) -> None:
    def raise_connect_error(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", raise_connect_error)
    try:
        ollama.ask([{"role": "user", "content": "hi"}])
        assert False, "OllamaError를 기대했지만 예외가 발생하지 않았어요"
    except ollama.OllamaError:
        pass


def test_ollama_ask_raises_on_empty_response(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse("   "))
    try:
        ollama.ask([{"role": "user", "content": "hi"}])
        assert False, "OllamaError를 기대했지만 예외가 발생하지 않았어요"
    except ollama.OllamaError:
        pass


def test_ollama_ask_raises_on_non_json_response(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _NonJsonResponse())
    try:
        ollama.ask([{"role": "user", "content": "hi"}])
        assert False, "OllamaError를 기대했지만 예외가 발생하지 않았어요"
    except ollama.OllamaError:
        pass


def test_ollama_ask_raises_on_null_message(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _NullMessageResponse())
    try:
        ollama.ask([{"role": "user", "content": "hi"}])
        assert False, "OllamaError를 기대했지만 예외가 발생하지 않았어요"
    except ollama.OllamaError:
        pass


def test_templates_fallback_r01_mentions_main() -> None:
    assert "main" in templates.fallback("R01", {})


def test_templates_fallback_r03_includes_filename() -> None:
    text = templates.fallback("R03", {"files": [".env"]})
    assert ".env" in text


def test_templates_fallback_unknown_rule_has_default_text() -> None:
    assert templates.fallback("R99", {}) == templates._DEFAULT


def test_cache_roundtrip(tmp_path, monkeypatch) -> None:
    _use_tmp_cache(tmp_path, monkeypatch)
    key = cache.make_key("R01", {"push_branch": "main"})
    assert cache.get(key) is None
    cache.set(key, "캐시된 설명")
    assert cache.get(key) == "캐시된 설명"


def test_cache_key_is_order_independent_for_facts() -> None:
    key1 = cache.make_key("R01", {"a": 1, "b": 2})
    key2 = cache.make_key("R01", {"b": 2, "a": 1})
    assert key1 == key2


def test_cache_get_returns_none_when_file_corrupted(tmp_path, monkeypatch) -> None:
    _use_tmp_cache(tmp_path, monkeypatch)
    cache.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache.CACHE_PATH.write_text('{"R01": "half', encoding="utf-8")
    assert cache.get(cache.make_key("R01", {})) is None


def test_cache_set_recovers_from_corrupted_file(tmp_path, monkeypatch) -> None:
    _use_tmp_cache(tmp_path, monkeypatch)
    cache.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache.CACHE_PATH.write_text('{"R01": "half', encoding="utf-8")

    key = cache.make_key("R02", {})
    cache.set(key, "새 설명")
    assert cache.get(key) == "새 설명"


def test_explain_uses_ollama_result_and_caches_it(tmp_path, monkeypatch) -> None:
    _use_tmp_cache(tmp_path, monkeypatch)
    monkeypatch.setattr(ollama, "ask", lambda messages: "Ollama 설명")

    result = explain_module.explain(
        "R01", "보호된 브랜치(main) 직접 push", {"push_branch": "main"}
    )
    assert result.text == "Ollama 설명"
    assert result.llm_used is True

    key = cache.make_key("R01", {"push_branch": "main"})
    assert cache.get(key) == "Ollama 설명"


def test_explain_falls_back_to_template_on_ollama_error(tmp_path, monkeypatch) -> None:
    _use_tmp_cache(tmp_path, monkeypatch)

    def raise_error(messages):
        raise ollama.OllamaError("down")

    monkeypatch.setattr(ollama, "ask", raise_error)

    result = explain_module.explain(
        "R01", "보호된 브랜치(main) 직접 push", {"push_branch": "main"}
    )
    assert result.llm_used is False
    assert result.text == templates.fallback("R01", {"push_branch": "main"})

    key = cache.make_key("R01", {"push_branch": "main"})
    assert cache.get(key) is None, "템플릿 폴백 결과는 캐시하지 않아야 해요"


def test_explain_cache_hit_skips_ollama_call(tmp_path, monkeypatch) -> None:
    _use_tmp_cache(tmp_path, monkeypatch)
    key = cache.make_key("R02", {"push_branch": "main"})
    cache.set(key, "이미 캐시된 설명")

    def fail_if_called(messages):
        raise AssertionError("캐시 적중 시 Ollama를 호출하면 안 돼요")

    monkeypatch.setattr(ollama, "ask", fail_if_called)

    result = explain_module.explain("R02", "force push", {"push_branch": "main"})
    assert result.text == "이미 캐시된 설명"
    assert result.llm_used is True


def test_explain_recovers_when_cache_file_is_corrupted(tmp_path, monkeypatch) -> None:
    _use_tmp_cache(tmp_path, monkeypatch)
    cache.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache.CACHE_PATH.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(ollama, "ask", lambda messages: "복구된 설명")

    result = explain_module.explain("R01", "t", {"push_branch": "main"})
    assert result.text == "복구된 설명"
    assert result.llm_used is True
    assert cache.get(cache.make_key("R01", {"push_branch": "main"})) == "복구된 설명"


def test_explain_falls_back_to_template_when_ollama_returns_null_message(
    tmp_path, monkeypatch
) -> None:
    _use_tmp_cache(tmp_path, monkeypatch)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _NullMessageResponse())

    result = explain_module.explain("R01", "t", {"push_branch": "main"})
    assert result.llm_used is False
    assert result.text == templates.fallback("R01", {"push_branch": "main"})
