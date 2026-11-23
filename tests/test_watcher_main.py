from watcher import __main__ as watcher_main
from watcher.config import WatcherConfigError


def test_main_returns_1_when_load_config_fails(monkeypatch, caplog) -> None:
    def fake_load_config():
        raise WatcherConfigError("토큰이 필요해요")

    monkeypatch.setattr(watcher_main, "load_config", fake_load_config)

    exit_code = watcher_main.main()

    assert exit_code == 1
    assert "토큰이 필요해요" in caplog.text


def test_main_returns_1_when_run_forever_raises_config_error(
    monkeypatch, caplog
) -> None:
    monkeypatch.setattr(watcher_main, "load_config", lambda: object())
    monkeypatch.setattr(
        watcher_main.ollama_health, "check", lambda config: (True, "ok")
    )

    def fake_run_forever(config):
        raise WatcherConfigError(
            "repos에 owner/repo가 없어요. DB 담당에게 seed 등록을 요청하세요."
        )

    monkeypatch.setattr(watcher_main.poller, "run_forever", fake_run_forever)

    exit_code = watcher_main.main()

    assert exit_code == 1
    assert "repos에 owner/repo가 없어요" in caplog.text


def test_main_returns_0_on_success(monkeypatch) -> None:
    monkeypatch.setattr(watcher_main, "load_config", lambda: object())
    monkeypatch.setattr(
        watcher_main.ollama_health, "check", lambda config: (True, "ok")
    )
    monkeypatch.setattr(watcher_main.poller, "run_forever", lambda config: None)

    assert watcher_main.main() == 0
