import shutil
import subprocess
from pathlib import Path

BASHRC_PATH = Path.home() / ".bashrc"
BASH_PROFILE_PATH = Path.home() / ".bash_profile"
ZSHRC_PATH = Path.home() / ".zshrc"

_MARKER_START = "# >>> gitcoach git wrapper >>>"
_MARKER_END = "# <<< gitcoach git wrapper <<<"

_BASH_BLOCK = f'{_MARKER_START}\ngit() {{ gitcoach run -- "$@"; }}\n{_MARKER_END}\n'
_POWERSHELL_BLOCK = (
    f"{_MARKER_START}\nfunction git {{ & gitcoach run -- @args }}\n{_MARKER_END}\n"
)


def _bash_targets() -> tuple[tuple[str, Path], ...]:
    """모듈 속성을 매번 다시 읽는다 — 테스트에서 `BASHRC_PATH` 등을 monkeypatch해도
    반영되도록 import 시점에 튜플로 고정하지 않는다."""
    return (
        ("bash (~/.bashrc)", BASHRC_PATH),
        ("bash (~/.bash_profile)", BASH_PROFILE_PATH),
    )


def powershell_profile_path() -> Path | None:
    """`$PROFILE`을 동적으로 물어본다. Windows PowerShell 5.1과 PowerShell 7+의
    프로필 경로가 달라서 하드코딩하지 않는다. pwsh(7+)가 있으면 그걸 우선한다."""
    for exe in ("pwsh", "powershell"):
        if shutil.which(exe) is None:
            continue
        try:
            result = subprocess.run(
                [exe, "-NoProfile", "-Command", "$PROFILE"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        output = result.stdout.strip()
        if result.returncode == 0 and output:
            return Path(output)
    return None


def _upsert_block(path: Path, block: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    start = existing.find(_MARKER_START)
    end = existing.find(_MARKER_END)
    if start != -1 and end != -1:
        new_content = existing[:start] + block + existing[end + len(_MARKER_END) :]
    else:
        sep = "" if not existing or existing.endswith("\n") else "\n"
        new_content = existing + sep + block
    if new_content == existing:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_content, encoding="utf-8")


def _remove_block(path: Path) -> bool:
    if not path.exists():
        return False
    existing = path.read_text(encoding="utf-8")
    start = existing.find(_MARKER_START)
    end = existing.find(_MARKER_END)
    if start == -1 or end == -1:
        return False
    new_content = existing[:start] + existing[end + len(_MARKER_END) :]
    path.write_text(new_content, encoding="utf-8")
    return True


def _has_block(path: Path) -> bool:
    if not path.exists():
        return False
    return _MARKER_START in path.read_text(encoding="utf-8")


def install() -> list[str]:
    installed = []
    for label, path in _bash_targets():
        _upsert_block(path, _BASH_BLOCK)
        installed.append(label)
    if ZSHRC_PATH.exists():
        _upsert_block(ZSHRC_PATH, _BASH_BLOCK)
        installed.append("zsh (~/.zshrc)")
    ps_path = powershell_profile_path()
    if ps_path is not None:
        _upsert_block(ps_path, _POWERSHELL_BLOCK)
        installed.append(f"powershell ({ps_path})")
    return installed


def uninstall() -> list[str]:
    removed = []
    for label, path in (*_bash_targets(), ("zsh (~/.zshrc)", ZSHRC_PATH)):
        if _remove_block(path):
            removed.append(label)
    ps_path = powershell_profile_path()
    if ps_path is not None and _remove_block(ps_path):
        removed.append(f"powershell ({ps_path})")
    return removed


def status() -> dict[str, bool]:
    result = {label: _has_block(path) for label, path in _bash_targets()}
    result["zsh (~/.zshrc)"] = _has_block(ZSHRC_PATH)
    ps_path = powershell_profile_path()
    result["powershell"] = ps_path is not None and _has_block(ps_path)
    return result
