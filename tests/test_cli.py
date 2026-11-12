from typer.testing import CliRunner

from gitcoach import __version__, config, sync, wrapper
from gitcoach import doctor as doctor_module
from gitcoach.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_run_command(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("gitcoach.shim.run", lambda argv: calls.append(argv) or 0)
    result = runner.invoke(app, ["run", "--", "status"])
    assert result.exit_code == 0
    assert calls == [["status"]]


def _use_tmp_repo_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "find_repo_root", lambda: tmp_path)


def _use_tmp_global_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "GLOBAL_CONFIG_PATH", tmp_path / "config.toml")


def test_config_show_displays_effective_settings(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_config(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "protected = ['main']" in result.stdout
    assert "ollama.url" in result.stdout


def test_config_protected_sets_and_reads_back(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_config(tmp_path, monkeypatch)
    runner.invoke(app, ["config", "protected", "main", "develop"])
    result = runner.invoke(app, ["config", "protected"])
    assert result.exit_code == 0
    assert "main, develop" in result.stdout


def test_config_disable_rule_r03_is_blocked(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_config(tmp_path, monkeypatch)
    result = runner.invoke(app, ["config", "disable-rule", "R03"])
    assert result.exit_code == 1
    assert "R03은 끌 수 없어요" in result.stdout


def test_config_disable_then_enable_rule(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_config(tmp_path, monkeypatch)
    runner.invoke(app, ["config", "disable-rule", "R05"])
    assert config.disabled_rules(tmp_path) == {"R05"}
    runner.invoke(app, ["config", "enable-rule", "R05"])
    assert config.disabled_rules(tmp_path) == set()


def test_config_ollama_warns_when_env_var_overrides(tmp_path, monkeypatch) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    monkeypatch.setenv("OLLAMA_URL", "http://example:1234")
    result = runner.invoke(app, ["config", "ollama", "--url", "http://new:1"])
    assert result.exit_code == 0
    assert "OLLAMA_URL" in result.stdout


def test_config_ollama_no_warning_without_env_var(tmp_path, monkeypatch) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    result = runner.invoke(app, ["config", "ollama", "--url", "http://new:1"])
    assert result.exit_code == 0
    assert "OLLAMA_URL" not in result.stdout


def _outside_repo(monkeypatch) -> None:
    monkeypatch.setattr(config, "find_repo_root", lambda: None)


def test_config_protected_outside_repo_shows_message_not_traceback(monkeypatch) -> None:
    _outside_repo(monkeypatch)
    result = runner.invoke(app, ["config", "protected", "main"])
    assert result.exit_code == 1
    assert "레포 밖에서는" in result.stdout


def test_config_enable_rule_outside_repo_shows_message_not_traceback(
    monkeypatch,
) -> None:
    _outside_repo(monkeypatch)
    result = runner.invoke(app, ["config", "enable-rule", "R05"])
    assert result.exit_code == 1
    assert "레포 밖에서는" in result.stdout


def test_sync_command_prints_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        sync,
        "push_events",
        lambda: sync.SyncResult(inserted=2, duplicate=1, rejected=[]),
    )
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "새로 저장 2건" in result.stdout
    assert "중복(이미 저장됨) 1건" in result.stdout


def test_sync_command_prints_rejected_reasons(monkeypatch) -> None:
    monkeypatch.setattr(
        sync,
        "push_events",
        lambda: sync.SyncResult(
            inserted=0, duplicate=0, rejected=[("ev-1", "형식 오류")]
        ),
    )
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "거절됨 1건" in result.stdout
    assert "ev-1: 형식 오류" in result.stdout


def test_sync_command_shows_message_not_traceback_when_env_missing(
    monkeypatch,
) -> None:
    def fake_push_events():
        raise sync.SyncError("환경변수가 필요해요")

    monkeypatch.setattr(sync, "push_events", fake_push_events)
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 1
    assert "환경변수가 필요해요" in result.stdout


# ---- init (12번) ----


def test_init_installs_wrapper_and_detects_member_via_gh(monkeypatch) -> None:
    monkeypatch.setattr(wrapper, "install", lambda: ["bash (~/.bashrc)"])
    monkeypatch.setattr(config, "member", lambda: None)
    monkeypatch.setattr(config, "detect_github_login", lambda: "octocat")
    saved = {}
    monkeypatch.setattr(
        config, "set_member", lambda login: saved.setdefault("login", login)
    )
    monkeypatch.setattr(doctor_module, "check_ollama", lambda: (True, "Ollama 연결됨"))
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert saved["login"] == "octocat"
    assert "bash (~/.bashrc)" in result.stdout


def test_init_falls_back_to_manual_prompt_when_gh_detection_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(wrapper, "install", list)
    monkeypatch.setattr(config, "member", lambda: None)
    monkeypatch.setattr(config, "detect_github_login", lambda: None)
    saved = {}
    monkeypatch.setattr(
        config, "set_member", lambda login: saved.setdefault("login", login)
    )
    monkeypatch.setattr(
        doctor_module, "check_ollama", lambda: (False, "Ollama에 연결할 수 없어요")
    )
    result = runner.invoke(app, ["init"], input="ManualUser\n")
    assert result.exit_code == 0
    assert saved["login"] == "manualuser"


def test_init_skips_detection_when_member_already_set(monkeypatch) -> None:
    monkeypatch.setattr(wrapper, "install", list)
    monkeypatch.setattr(config, "member", lambda: "existing")
    called = []
    monkeypatch.setattr(config, "detect_github_login", lambda: called.append(1) or "x")
    monkeypatch.setattr(doctor_module, "check_ollama", lambda: (True, "ok"))
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert called == []
    assert "이미 설정된 member: existing" in result.stdout


# ---- doctor (결정 5번: git·래퍼만 치명적, Ollama는 경고) ----


def test_doctor_exit_code_1_when_git_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        doctor_module, "check_git", lambda: (False, "git을 찾을 수 없어요")
    )
    monkeypatch.setattr(doctor_module, "check_ollama", lambda: (True, "ok"))
    monkeypatch.setattr(doctor_module, "check_wrapper", lambda: {"bash": True})
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1


def test_doctor_exit_code_1_when_no_wrapper_installed(monkeypatch) -> None:
    monkeypatch.setattr(doctor_module, "check_git", lambda: (True, "git 설치됨"))
    monkeypatch.setattr(doctor_module, "check_ollama", lambda: (True, "ok"))
    monkeypatch.setattr(
        doctor_module, "check_wrapper", lambda: {"bash": False, "zsh": False}
    )
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1


def test_doctor_exit_code_0_when_ollama_down_but_wrapper_installed(
    monkeypatch,
) -> None:
    monkeypatch.setattr(doctor_module, "check_git", lambda: (True, "git 설치됨"))
    monkeypatch.setattr(
        doctor_module, "check_ollama", lambda: (False, "Ollama에 연결할 수 없어요")
    )
    monkeypatch.setattr(doctor_module, "check_wrapper", lambda: {"bash": True})
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "⚠️" in result.stdout


# ---- uninstall (결정 6번: 래퍼만 제거) ----


def test_uninstall_reports_removed_targets(monkeypatch) -> None:
    monkeypatch.setattr(wrapper, "uninstall", lambda: ["bash (~/.bashrc)"])
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    assert "bash (~/.bashrc)" in result.stdout


def test_uninstall_when_nothing_installed_shows_friendly_message(
    monkeypatch,
) -> None:
    monkeypatch.setattr(wrapper, "uninstall", list)
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    assert "제거할 쉘 래퍼가 없어요" in result.stdout
