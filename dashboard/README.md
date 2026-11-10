# Git Coach 대시보드 (dashboard/)

팀 Git 협업 위반 기록, 통계, 복습 퀴즈를 보여 주는 웹 대시보드입니다. v0.1은 읽기 전용입니다.

- 스택: Next.js 16 (App Router) · TypeScript · Tailwind CSS 4
- 화면 구성·디자인 규칙: [`docs/wireframes/README.md`](../docs/wireframes/README.md)
- 개발 가이드: 웹 대시보드 역할 가이드(임지윤)

## 실행

```bash
cd dashboard
npm install      # 처음 한 번
npm run dev      # http://localhost:3000
```

## 확인 명령 (CI와 같음)

```bash
npm run lint       # ESLint
npm run typecheck  # TypeScript 타입 체크
npm run build      # 프로덕션 빌드
```

## mock 데이터

v0.1은 레포 맨 위 `samples/*.json`(스키마 v1 더미)을 `lib/data/mock/sample-events.json` 한 파일로 합쳐 씁니다.
대시보드는 `dashboard/` 안에서만 빌드되기 때문에(Docker 포함) 바깥 폴더를 직접 읽지 않고 복사해 둡니다.

```bash
npm run samples:sync   # samples/ 가 바뀌면 다시 실행하고 결과 파일을 커밋
```

## 폴더

| 경로 | 내용 |
|---|---|
| `app/` | 페이지 (`/`, `/events`, `/me`, `/quiz`, `/rules`) |
| `components/` | 화면 공용 컴포넌트 |
| `lib/data/` | 데이터 계층. **화면은 여기 함수만 호출합니다** (mock → Supabase 교체 지점) |
| `lib/labels.ts` | 이벤트 값 → 화면 문구 |
| `types/event.ts` | 이벤트 스키마 v1 타입 (`docs/guide/01_cli.md` 6절과 같음) |

## 환경변수

| 이름 | 용도 | 시점 |
|---|---|---|
| `NEXT_PUBLIC_CURRENT_USER` | 로그인 전 "현재 사용자" (github_login) | v0.1 |
| `NEXT_PUBLIC_DATA_SOURCE` | `mock` / `supabase` | mock 데이터 계층부터 |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase 연결 (anon 키만) | 11/19~20 |

실제 값은 `.env.local`에만 둡니다. `.env*`는 `.gitignore`에 들어 있습니다. 서버 키(`service_role`)는 웹에 절대 넣지 않습니다.
