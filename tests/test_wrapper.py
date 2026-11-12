from gitcoach import wrapper


def _set_paths(tmp_path, monkeypatch, *, zshrc_exists: bool = False) -> None:
    monkeypatch.setattr(wrapper, "BASHRC_PATH", tmp_path / "bashrc")
    monkeypatch.setattr(wrapper, "BASH_PROFILE_PATH", tmp_path / "bash_profile")
    zshrc = tmp_path / "zshrc"
    if zshrc_exists:
        zshrc.write_text("# existing zsh config\n", encoding="utf-8")
    monkeypatch.setattr(wrapper, "ZSHRC_PATH", zshrc)
    monkeypatch.setattr(wrapper, "powershell_profile_path", lambda: None)


# ---- install: Git Bash 로그인 쉘 문제 (결정 1번) ----


def test_install_writes_both_bashrc_and_bash_profile(tmp_path, monkeypatch) -> None:
    _set_paths(tmp_path, monkeypatch)
    installed = wrapper.install()
    assert wrapper.BASHRC_PATH.exists()
    assert wrapper.BASH_PROFILE_PATH.exists()
    assert "gitcoach run" in wrapper.BASHRC_PATH.read_text(encoding="utf-8")
    assert "gitcoach run" in wrapper.BASH_PROFILE_PATH.read_text(encoding="utf-8")
    assert "bash (~/.bashrc)" in installed
    assert "bash (~/.bash_profile)" in installed


def test_install_skips_zsh_when_zshrc_does_not_exist(tmp_path, monkeypatch) -> None:
    _set_paths(tmp_path, monkeypatch, zshrc_exists=False)
    installed = wrapper.install()
    assert not wrapper.ZSHRC_PATH.exists()
    assert not any("zsh" in item for item in installed)


def test_install_updates_zsh_when_zshrc_already_exists(tmp_path, monkeypatch) -> None:
    _set_paths(tmp_path, monkeypatch, zshrc_exists=True)
    installed = wrapper.install()
    assert "gitcoach run" in wrapper.ZSHRC_PATH.read_text(encoding="utf-8")
    assert any("zsh" in item for item in installed)


def test_install_includes_powershell_when_profile_resolved(
    tmp_path, monkeypatch
) -> None:
    _set_paths(tmp_path, monkeypatch)
    ps_profile = tmp_path / "profile.ps1"
    monkeypatch.setattr(wrapper, "powershell_profile_path", lambda: ps_profile)
    installed = wrapper.install()
    assert ps_profile.exists()
    assert "function git" in ps_profile.read_text(encoding="utf-8")
    assert any("powershell" in item for item in installed)


# ---- idempotency (결정 2번) ----


def test_install_twice_does_not_duplicate_block(tmp_path, monkeypatch) -> None:
    _set_paths(tmp_path, monkeypatch)
    wrapper.install()
    wrapper.install()
    content = wrapper.BASHRC_PATH.read_text(encoding="utf-8")
    assert content.count(wrapper._MARKER_START) == 1


def test_install_preserves_existing_content_around_block(tmp_path, monkeypatch) -> None:
    _set_paths(tmp_path, monkeypatch)
    wrapper.BASHRC_PATH.write_text("export PATH=foo\n", encoding="utf-8")
    wrapper.install()
    content = wrapper.BASHRC_PATH.read_text(encoding="utf-8")
    assert "export PATH=foo" in content
    assert "gitcoach run" in content


# ---- uninstall (결정 6번: 래퍼만 제거) ----


def test_uninstall_removes_block_but_keeps_other_content(tmp_path, monkeypatch) -> None:
    _set_paths(tmp_path, monkeypatch)
    wrapper.BASHRC_PATH.write_text("export PATH=foo\n", encoding="utf-8")
    wrapper.install()
    removed = wrapper.uninstall()
    content = wrapper.BASHRC_PATH.read_text(encoding="utf-8")
    assert "gitcoach run" not in content
    assert "export PATH=foo" in content
    assert "bash (~/.bashrc)" in removed


def test_uninstall_when_nothing_installed_returns_empty_list(
    tmp_path, monkeypatch
) -> None:
    _set_paths(tmp_path, monkeypatch)
    assert wrapper.uninstall() == []


# ---- status ----


def test_status_reflects_install_and_uninstall(tmp_path, monkeypatch) -> None:
    _set_paths(tmp_path, monkeypatch)
    assert not any(wrapper.status().values())
    wrapper.install()
    status = wrapper.status()
    assert status["bash (~/.bashrc)"] is True
    assert status["bash (~/.bash_profile)"] is True
    wrapper.uninstall()
    assert not any(wrapper.status().values())
