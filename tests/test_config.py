import subprocess
import tomllib

from gitcoach import config


def _init_repo(tmp_path) -> None:
    subprocess.run(["git", "init", "-b", "main"], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "config", "user.name", "t"], check=True)


def _use_tmp_global_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "GLOBAL_CONFIG_PATH", tmp_path / "config.toml")


# ---- 기본값 (파일 없음) ----


def test_protected_branches_default_when_no_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    assert config.protected_branches() == ["main"]


def test_disabled_rules_default_when_no_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    assert config.disabled_rules() == set()


def test_member_default_when_no_file(tmp_path, monkeypatch) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    assert config.member() is None


def test_ollama_settings_default_when_no_file(tmp_path, monkeypatch) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    settings = config.ollama_settings()
    assert settings.url == "http://localhost:11434"
    assert settings.model == "gemma4:e2b"


# ---- 레포/전역 toml에서 읽기 ----


def test_protected_branches_reads_repo_toml(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_text('protected = ["main", "develop"]')
    assert config.protected_branches() == ["main", "develop"]


def test_member_reads_global_toml(tmp_path, monkeypatch) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    config.GLOBAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.GLOBAL_CONFIG_PATH.write_text('member = "octocat"')
    assert config.member() == "octocat"


def test_ollama_settings_reads_global_toml(tmp_path, monkeypatch) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    config.GLOBAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.GLOBAL_CONFIG_PATH.write_text(
        '[ollama]\nurl = "http://host:1234"\nmodel = "m"'
    )
    settings = config.ollama_settings()
    assert settings.url == "http://host:1234"
    assert settings.model == "m"


def test_ollama_url_env_var_overrides_config(tmp_path, monkeypatch) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    config.GLOBAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.GLOBAL_CONFIG_PATH.write_text('[ollama]\nurl = "http://host:1234"')
    monkeypatch.setenv("OLLAMA_URL", "http://env:9999")
    assert config.ollama_settings().url == "http://env:9999"


# ---- set_* read-modify-write (다른 키 보존) ----


def test_set_protected_branches_preserves_disabled_rules(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    config.disable_rule("R05")
    config.set_protected_branches(["main", "develop"])
    assert config.protected_branches() == ["main", "develop"]
    assert config.disabled_rules() == {"R05"}


def test_set_ollama_settings_updates_only_given_field(tmp_path, monkeypatch) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    config.set_ollama_settings(url="http://host:1234", model="m1")
    config.set_ollama_settings(model="m2")
    settings = config.ollama_settings()
    assert settings.url == "http://host:1234"
    assert settings.model == "m2"


def test_disable_then_enable_rule_toggles(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    config.disable_rule("R05")
    assert config.disabled_rules() == {"R05"}
    config.enable_rule("R05")
    assert config.disabled_rules() == set()


# ---- R03 가드 (결정 1번) ----


def test_disabled_rules_always_excludes_r03_even_if_written_manually(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_text('disabled_rules = ["R03", "R05"]')
    assert config.disabled_rules() == {"R05"}


def test_disable_rule_r03_raises_value_error(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    try:
        config.disable_rule("R03")
        assert False, "ValueError를 기대했지만 발생하지 않았어요"
    except ValueError:
        pass
    assert config.disabled_rules() == set()


# ---- 깨진 설정 폴백 (결정 4번) ----


def test_protected_branches_falls_back_on_broken_toml_syntax(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_text("protected = [")
    assert config.protected_branches() == ["main"]


def test_protected_branches_falls_back_on_invalid_utf8(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_bytes(b"protected = \xff\xfe\n")
    assert config.protected_branches() == ["main"]


def test_protected_branches_falls_back_when_not_a_list(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_text('protected = "main"')
    assert config.protected_branches() == ["main"]


def test_disabled_rules_falls_back_when_elements_not_strings(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_text("disabled_rules = [1, 2]")
    assert config.disabled_rules() == set()


# ---- repo_root sentinel (결정 2번) ----


def test_protected_branches_calls_find_repo_root_when_arg_omitted(
    tmp_path, monkeypatch
) -> None:
    calls = []
    monkeypatch.setattr(config, "find_repo_root", lambda: calls.append(1) or None)
    config.protected_branches()
    assert calls == [1]


def test_protected_branches_does_not_call_find_repo_root_when_none_given(
    monkeypatch,
) -> None:
    def fail_if_called():
        raise AssertionError("명시적 None이면 find_repo_root를 호출하면 안 돼요")

    monkeypatch.setattr(config, "find_repo_root", fail_if_called)
    assert config.protected_branches(repo_root=None) == ["main"]


# ---- _dump_toml 라운드트립 (결정 3번) ----


def test_dump_toml_roundtrip_with_quotes_and_backslashes(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    tricky = ['feature/x"y', "http://host:11434/a\\b"]
    config.set_protected_branches(tricky)
    with (tmp_path / ".gitcoach.toml").open("rb") as f:
        loaded = tomllib.load(f)
    assert loaded["protected"] == tricky
    assert config.protected_branches() == tricky


# ---- 쓰기 경로는 깨진 파일을 덮어쓰지 않고 에러로 멈춘다 (리뷰 1번) ----


def test_set_protected_branches_raises_on_broken_file_instead_of_overwriting(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_text('protected = ["main", "release"\n')
    try:
        config.set_protected_branches(["main"])
        assert False, "ValueError를 기대했지만 발생하지 않았어요"
    except ValueError:
        pass
    assert (
        tmp_path / ".gitcoach.toml"
    ).read_text() == 'protected = ["main", "release"\n'


def test_disable_rule_raises_on_broken_file_instead_of_overwriting(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_bytes(b"disabled_rules = \xff\xfe\n")
    try:
        config.disable_rule("R05")
        assert False, "ValueError를 기대했지만 발생하지 않았어요"
    except ValueError:
        pass


def test_set_ollama_settings_raises_on_broken_global_file(
    tmp_path, monkeypatch
) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    config.GLOBAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.GLOBAL_CONFIG_PATH.write_text("[ollama")
    try:
        config.set_ollama_settings(url="http://new:1")
        assert False, "ValueError를 기대했지만 발생하지 않았어요"
    except ValueError:
        pass
    assert config.GLOBAL_CONFIG_PATH.read_text() == "[ollama"


# ---- 숫자·불린 값은 보존한 채 다른 키를 쓸 수 있어야 한다 (리뷰 4번) ----


def test_disable_rule_preserves_unrelated_non_string_values(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_text("max_files = 3\nverbose = true\n")
    config.disable_rule("R05")
    with (tmp_path / ".gitcoach.toml").open("rb") as f:
        loaded = tomllib.load(f)
    assert loaded["max_files"] == 3
    assert loaded["verbose"] is True
    assert loaded["disabled_rules"] == ["R05"]


# ---- disabled_rules()는 대소문자를 정규화해서 읽는다 (리뷰 5번) ----


def test_disabled_rules_normalizes_lowercase_entries(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_text('disabled_rules = ["r05"]')
    assert config.disabled_rules() == {"R05"}


def test_disabled_rules_normalizes_lowercase_r03_and_still_excludes_it(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_text('disabled_rules = ["r03", "r05"]')
    assert config.disabled_rules() == {"R05"}


# ---- set_member / detect_github_login (12번) ----


def test_set_member_writes_and_reads_back(tmp_path, monkeypatch) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    config.set_member("octocat")
    assert config.member() == "octocat"


def test_set_member_preserves_ollama_settings(tmp_path, monkeypatch) -> None:
    _use_tmp_global_config(tmp_path, monkeypatch)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    config.set_ollama_settings(url="http://host:1234")
    config.set_member("octocat")
    assert config.member() == "octocat"
    assert config.ollama_settings().url == "http://host:1234"


def test_detect_github_login_parses_gh_output_lowercased(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        assert cmd == ["gh", "api", "user"]
        return subprocess.CompletedProcess(cmd, 0, stdout='{"login": "Octocat"}')

    monkeypatch.setattr(config.subprocess, "run", fake_run)
    assert config.detect_github_login() == "octocat"


def test_detect_github_login_returns_none_when_gh_not_installed(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(config.subprocess, "run", fake_run)
    assert config.detect_github_login() is None


def test_detect_github_login_returns_none_on_nonzero_exit(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not logged in")

    monkeypatch.setattr(config.subprocess, "run", fake_run)
    assert config.detect_github_login() is None


def test_detect_github_login_returns_none_on_invalid_json(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="not json")

    monkeypatch.setattr(config.subprocess, "run", fake_run)
    assert config.detect_github_login() is None


def test_detect_github_login_returns_none_when_login_field_missing(
    monkeypatch,
) -> None:
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="{}")

    monkeypatch.setattr(config.subprocess, "run", fake_run)
    assert config.detect_github_login() is None
