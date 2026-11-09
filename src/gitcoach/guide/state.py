import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from gitcoach.models import GuideState, ViolationSnapshot


def _git_dir() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def _state_path() -> Path:
    return _git_dir() / "gitcoach" / "guide.json"


def load() -> GuideState | None:
    path = _state_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    queue = [ViolationSnapshot(**item) for item in data["queue"]]
    return GuideState(
        queue=queue,
        step_index=data["step_index"],
        hint_count=data["hint_count"],
    )


def save(guide_state: GuideState) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "queue": [asdict(snap) for snap in guide_state.queue],
        "step_index": guide_state.step_index,
        "hint_count": guide_state.hint_count,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear() -> None:
    path = _state_path()
    if path.exists():
        path.unlink()
