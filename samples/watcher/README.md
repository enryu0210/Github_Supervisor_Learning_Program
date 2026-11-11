# watcher DB 적재 샘플 (#44)

11/14~16 DB 마이그레이션 PR에서 `prs`·`pr_reviews` 제약을 시험하는 용도의 샘플입니다. 필드는 `01_cli.md` 5절 기준, DB 적재 시 `repo`·`pr_number`는 `prs` upsert로 받은 `id`(`pr_id`)로 변환합니다(#44 체크리스트 동의 사항).

## 파일
- `prs_sample.json` — PR 6건. `number: 104`는 `last_activity_at`이 11/7이라 3일 기준(D3) 방치 PR 판정 테스트용입니다.
- `pr_reviews_sample.json` — 리뷰 7건, `APPROVED`·`COMMENTED`·`DISMISSED` 섞음. `review_id`는 GitHub 네이티브 id를 가정한 bigint 값입니다.
- `pr_reviews_dismiss_upsert_example.json` — 같은 `review_id`가 `APPROVED` → `DISMISSED`로 바뀌는 두 시점(`poll_1`/`poll_2`)을 보여줍니다. `pr_reviews`는 `review_id` 기준 upsert이므로 `poll_2`를 적재하면 같은 행이 `DISMISSED`로 갱신돼야 합니다(두 객체를 한 배치로 같이 넣는 샘플이 아닙니다).

## 의도적으로 뺀 것
- `PENDING` 상태 리뷰는 포함하지 않았습니다 — 제출 전 리뷰는 보내지 않기로 합의했습니다(#44).
- 리뷰 `body`는 필드 자체를 넣지 않았습니다(#44 필드 목록에서 제외).
