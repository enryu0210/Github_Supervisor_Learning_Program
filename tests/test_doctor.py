import httpx

from gitcoach import doctor
from gitcoach.models import OllamaSettings


class _FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200) -> None:
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self) -> dict:
        return self._json


# ---- check_git ----


def test_check_git_found(monkeypatch) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/git")
    ok, message = doctor.check_git()
    assert ok
    assert "git" in message


def test_check_git_missing(monkeypatch) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    ok, _ = doctor.check_git()
    assert not ok


# ---- check_ollama (config.ollama_settings() 재사용, 결정 4번) ----


def test_check_ollama_model_found(monkeypatch) -> None:
    monkeypatch.setattr(
        doctor.config,
        "ollama_settings",
        lambda: OllamaSettings(url="http://x", model="gemma4:e2b"),
    )
    monkeypatch.setattr(
        doctor.httpx,
        "get",
        lambda url, timeout: _FakeResponse({"models": [{"name": "gemma4:e2b"}]}),
    )
    ok, message = doctor.check_ollama()
    assert ok
    assert "gemma4:e2b" in message


def test_check_ollama_model_not_pulled(monkeypatch) -> None:
    monkeypatch.setattr(
        doctor.config,
        "ollama_settings",
        lambda: OllamaSettings(url="http://x", model="gemma4:e2b"),
    )
    monkeypatch.setattr(
        doctor.httpx,
        "get",
        lambda url, timeout: _FakeResponse({"models": [{"name": "llama3"}]}),
    )
    ok, message = doctor.check_ollama()
    assert not ok
    assert "llama3" in message


def test_check_ollama_connection_error(monkeypatch) -> None:
    monkeypatch.setattr(
        doctor.config,
        "ollama_settings",
        lambda: OllamaSettings(url="http://x", model="m"),
    )

    def raise_connect_error(url, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(doctor.httpx, "get", raise_connect_error)
    ok, message = doctor.check_ollama()
    assert not ok
    assert "http://x" in message


def test_check_ollama_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(
        doctor.config,
        "ollama_settings",
        lambda: OllamaSettings(url="http://x", model="m"),
    )

    class _BadJsonResponse(_FakeResponse):
        def json(self) -> dict:
            raise ValueError("not json")

    monkeypatch.setattr(doctor.httpx, "get", lambda url, timeout: _BadJsonResponse({}))
    ok, _ = doctor.check_ollama()
    assert not ok


# ---- check_wrapper (wrapper.status() 위임) ----


def test_check_wrapper_delegates_to_wrapper_status(monkeypatch) -> None:
    monkeypatch.setattr(
        doctor.wrapper, "status", lambda: {"bash (~/.bashrc)": True, "zsh": False}
    )
    assert doctor.check_wrapper() == {"bash (~/.bashrc)": True, "zsh": False}
