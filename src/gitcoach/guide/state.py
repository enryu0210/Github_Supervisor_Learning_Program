import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path

from gitcoach.models import GuideState, ViolationSnapshot


def _git_dir() -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=False,  # 저장소 밖(clone·init 직전)에서도 래퍼가 죽지 않게
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def _state_path() -> Path | None:
    git_dir = _git_dir()
    if git_dir is None:
        return None
    return git_dir / "gitcoach" / "guide.json"


def load() -> GuideState | None:
    path = _state_path()
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        queue = [ViolationSnapshot(**item) for item in data["queue"]]
        return GuideState(
            queue=queue,
            step_index=data["step_index"],
            hint_count=data["hint_count"],
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        # guide 진행 중 Ctrl+C로 save() 쓰기가 끼어들면 파일이 반쯤 써진 채로
        # 남을 수 있다. 큐 내용을 복구할 수 없으니 guide_stopped 없이 포기하고
        # 손상된 파일을 지운다 — 지우지 않으면 이 레포의 모든 git 명령이 계속
        # 크래시한다(#64).
        path.unlink()
        return None


def save(guide_state: GuideState) -> None:
    path = _state_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "queue": [asdict(snap) for snap in guide_state.queue],
        "step_index": guide_state.step_index,
        "hint_count": guide_state.hint_count,
    }
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(tmp_path, path)


def clear() -> None:
    path = _state_path()
    if path is not None and path.exists():
        path.unlink()
