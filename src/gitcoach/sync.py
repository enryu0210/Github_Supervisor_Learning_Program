import os
from dataclasses import asdict, dataclass

import httpx

from gitcoach import events

SYNC_URL_ENV = "GITCOACH_SYNC_URL"
SYNC_TOKEN_ENV = "GITCOACH_SYNC_TOKEN"

BATCH_SIZE = 100
TIMEOUT = 15.0  # 원격 네트워크 호출이라 Ollama(로컬, 8초)보다 여유를 둔다


class SyncError(Exception):
    pass


@dataclass
class SyncResult:
    inserted: int
    duplicate: int
    rejected: list[tuple[str, str]]  # (event_id, reason)


def push_events() -> SyncResult:
    url = os.environ.get(SYNC_URL_ENV)
    token = os.environ.get(SYNC_TOKEN_ENV)
    if not url or not token:
        raise SyncError(
            f"환경변수 {SYNC_URL_ENV}·{SYNC_TOKEN_ENV}이 필요해요. "
            "환경변수로 설정한 뒤 다시 시도해 주세요(값은 이남주에게 문의)."
        )

    result = SyncResult(inserted=0, duplicate=0, rejected=[])
    while True:
        batch = events.unsynced(limit=BATCH_SIZE)
        if not batch:
            break

        response = _post_batch(url, token, batch)
        synced_ids = []
        rejected_ids = []
        for event_id, status, reason in _parse_response(response):
            if status == "inserted":
                result.inserted += 1
                synced_ids.append(event_id)
            elif status == "duplicate":
                result.duplicate += 1
                synced_ids.append(event_id)
            else:
                result.rejected.append((event_id, reason or "알 수 없는 이유"))
                rejected_ids.append(event_id)

        if synced_ids:
            events.mark_synced(synced_ids)
        if rejected_ids:
            # 거절 건을 synced=0으로 남기면 unsynced()가 매번 같은 거절 건부터
            # 돌려줘, 그 뒤에 쌓인 정상 이벤트가 영원히 전송되지 않는다. 영구
            # 제외해서 다음 배치가 그 뒤의 정상 이벤트로 넘어가게 한다.
            events.mark_rejected(rejected_ids)

        # 이번 배치에서 처리(전송 또는 거절 제외)된 게 하나도 없으면 다음
        # unsynced(100)도 똑같은 배치를 다시 돌려준다 — 무한 반복을 막기 위해 중단.
        if not synced_ids and not rejected_ids:
            break

    return result


def _post_batch(url: str, token: str, batch: list) -> dict:
    try:
        response = httpx.post(
            url,
            json={"events": [asdict(e) for e in batch]},
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SyncError(f"동기화 요청에 실패했어요: {exc}") from exc


def _parse_response(data: dict) -> list[tuple[str, str, str | None]]:
    """서버 응답 포맷은 가정이다({"results": [{"id","status","reason"}]}) —
    실제 Edge Function 계약은 11/17~18 이남주가 엔드포인트를 줄 때 확정되며,
    모양이 다르면 이 함수만 고치면 되도록 파싱을 여기 한 곳에 모아 둔다."""
    try:
        results = data.get("results", [])
        return [(r["id"], r["status"], r.get("reason")) for r in results]
    except (AttributeError, KeyError, TypeError) as exc:
        raise SyncError(f"서버 응답 형식이 예상과 달라요: {exc}") from exc
