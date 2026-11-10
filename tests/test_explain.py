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
