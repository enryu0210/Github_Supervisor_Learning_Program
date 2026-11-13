// 규칙 도감(/rules) 문장. 경고·가이드 문장은 CLI 와 똑같아야 하므로 직접 지어내지 않고 출처에서 옮긴다.
//   warning·consequence     → src/gitcoach/rules/r0x_*.py 의 _WARNING·_CONSEQUENCE (권아현)
//   guide                   → src/gitcoach/guide/scenarios.py 의 Scenario (권아현)
//   ifRun·undo·recovery     → docs/guide/01_cli.md 3-4 "그냥 실행 시 영향" 표
//   target·command·allowRun → docs/guide/01_cli.md 3-1 규칙 표
// CLI 쪽 문장이 바뀌면 여기도 같이 고친다. (11/13 develop 0d37d19 기준)
import type { Severity } from "@/types/event";

export type GuideStepDoc = { instruction: string; hint: string };

export type RuleDoc = {
  id: string;
  name: string;
  severity: Severity;
  /** 감지 대상 (3-1 표) */
  target: string;
  /** 감지하는 곳. CLI 명령 또는 watcher */
  detectedBy: string;
  /** [1] 그냥 실행 선택지가 있는가. null = 선택지 없음(watcher 전용) */
  allowRun: boolean | null;
  /** CLI 경고 한 줄 */
  warning: string;
  /** CLI 선택 화면의 "그냥 실행하면:" 한 줄 */
  consequence: string;
  /** 3-4 표: 그냥 실행하면 실제로 생기는 일 */
  ifRun: string;
  /** 3-4 표: 되돌리기 */
  undo: string;
  /** 3-4 표: 사후 복구 */
  recovery: string;
  guide: { title: string; summary: string; steps: GuideStepDoc[] } | null;
  /** 아직 CLI·watcher 에 문장이 없어 웹에서 임시로 쓴 부분이 있으면 true */
  draft?: boolean;
};

export const RULE_DOCS: RuleDoc[] = [
  {
    id: "R01",
    name: "main에 직접 push",
    severity: "high",
    target: "main에 직접 push (develop 제외)",
    detectedBy: "git push",
    allowRun: true,
    warning: "main 브랜치에 직접 push하려고 해요.",
    consequence: "리뷰·CI 없이 main에 들어가 배포까지 이어질 수 있어요.",
    ifRun: "보호가 있으면 서버가 거절해요. 없으면 리뷰·CI 없이 main에 들어가 Vercel 배포까지 이어질 수 있어요.",
    undo: "가능",
    recovery: "`git revert <커밋>` 후 push 해요. force push로 지우면 R02 문제가 생겨요.",
    guide: {
      title: "feature 브랜치로 옮겨 PR 올리기",
      summary: "main에는 직접 push하지 않고, feature 브랜치로 옮겨 PR로 올린다",
      steps: [
        { instruction: "지금 커밋을 가진 새 브랜치를 만드세요.", hint: "git switch -c feature/<영역>-<설명>" },
        { instruction: "새 브랜치를 내 fork(origin)에 올리세요.", hint: "git push -u origin <브랜치>" },
        { instruction: "upstream develop을 base로 PR을 올리세요.", hint: "gh pr create --base develop" },
      ],
    },
  },
  {
    id: "R02",
    name: "force push",
    severity: "high",
    target: "force push(-f, --force, +ref). --force-with-lease만이면 보통(medium)",
    detectedBy: "git push",
    allowRun: true,
    warning: "원격 기록을 덮어쓰는 force push를 하려고 해요.",
    consequence: "다른 사람이 올린 커밋이 사라질 수 있어요.",
    ifRun: "다른 사람 커밋이 원격에서 사라지고 그 사람의 로컬 기록이 갈라져요. PR 리뷰 댓글도 어긋나요.",
    undo: "대체로 가능",
    recovery: "커밋이 남은 팀원 PC에서 다시 push하거나 `git reflog`로 찾아요.",
    guide: {
      title: "원격 변경을 가져와 안전하게 push",
      summary: "force push 대신 pull --rebase로 맞추고 일반 push로 올린다",
      steps: [
        { instruction: "원격의 최신 변경을 먼저 가져오세요.", hint: "git pull --rebase (충돌 시 해결 후 git rebase --continue)" },
        { instruction: "이제 안전하게 push하세요.", hint: "git push" },
      ],
    },
  },
  {
    id: "R03",
    name: "비밀 정보 커밋",
    severity: "high",
    target: "비밀 정보 staged (.env, 개인키, 토큰 패턴)",
    detectedBy: "git add · commit · push",
    allowRun: false,
    warning: "비밀 정보가 담긴 파일이 staged 상태예요.",
    consequence: "허용 불가 — 그대로 커밋하면 기록에 영구히 남아요.",
    ifRun: "그냥 실행할 수 없어요. [q]를 고르면 명령이 막히고, [2]를 고르면 가이드로 넘어가요.",
    undo: "—",
    recovery: "—",
    guide: {
      title: "비밀 파일 빼고 .gitignore에 등록",
      summary: "비밀 파일은 스테이징에서 빼고 .gitignore로 다시 못 올라가게 막는다",
      steps: [
        { instruction: "스테이징에서 비밀 파일을 빼세요.", hint: "git restore --staged <파일>" },
        { instruction: ".gitignore에 비밀 파일 패턴을 추가하세요.", hint: ".gitignore 파일을 열어 추가하세요 (예: .env)" },
        { instruction: ".gitignore를 커밋에 포함하세요.", hint: "git add .gitignore" },
      ],
    },
  },
  {
    id: "R04",
    name: "main에서 직접 커밋",
    severity: "medium",
    target: "main에서 직접 커밋 (develop 제외)",
    detectedBy: "git commit",
    allowRun: true,
    warning: "main 브랜치에서 직접 커밋하려고 해요.",
    consequence: "로컬이라 당장 피해는 없지만, 다음 push에서 R01에 걸리고 원격과 어긋나 동기화가 꼬일 수 있어요.",
    ifRun: "로컬이라 당장 피해는 없어요. 다음 push에서 R01에 걸리고, 로컬 main이 원격과 갈라져 동기화가 실패해요.",
    undo: "가능",
    recovery: "`git branch feature/...`로 커밋을 옮긴 뒤 main을 원격 상태로 되돌려요.",
    guide: {
      title: "커밋을 feature 브랜치에서 하기",
      summary: "main에는 직접 커밋하지 않고, feature 브랜치로 옮겨서 커밋한다",
      steps: [
        { instruction: "지금 변경을 가진 새 브랜치를 만드세요.", hint: "git switch -c feature/<영역>-<설명>" },
        { instruction: "이제 feature 브랜치에서 커밋하세요.", hint: 'git commit -m "type(scope): 설명"' },
      ],
    },
  },
  {
    id: "R05",
    name: "브랜치명 규칙 위반",
    severity: "low",
    target: "브랜치명 규칙 위반 (feature|fix/<영역>-<설명>, docs/<설명>, release/vX.Y)",
    detectedBy: "git checkout -b · switch -c · branch",
    allowRun: true,
    warning: "브랜치 이름 '<이름>'이 규칙에 안 맞아요. 제안: <제안 이름>",
    consequence: "watcher가 다시 경고하고, pr-convention 검사가 실패하고, 대시보드 통계에서 빠질 수 있어요.",
    ifRun: "동작은 정상이에요. 하지만 watcher가 다시 경고하고, pr-convention 검사가 실패하고, 대시보드 통계에서 빠져요.",
    undo: "쉬움",
    recovery: "`git branch -m <새 이름>`으로 이름을 바꿔요.",
    guide: {
      title: "규칙에 맞는 브랜치명 쓰기",
      summary: "제안받은 이름으로 브랜치를 다시 만든다",
      steps: [
        { instruction: "위 경고에 나온 제안 이름으로 브랜치를 다시 만드세요.", hint: "git switch -c <제안 이름>" },
      ],
    },
  },
  {
    id: "R06",
    name: "커밋 메시지 규칙 위반",
    severity: "low",
    target: "커밋 메시지 규칙 위반 (type(scope): 설명)",
    detectedBy: "git commit -m",
    allowRun: true,
    warning: "커밋 메시지가 규칙에 안 맞아요.",
    consequence: "기록을 읽기 어려워지고, pr-convention 검사가 실패할 수 있어요.",
    ifRun: "기록을 읽기 어려워지고 pr-convention 검사가 실패해요.",
    undo: "push 전 쉬움",
    recovery: "push 전이면 `git commit --amend`로 고쳐요. push 후 amend는 force push가 필요해서 R02에 걸려요.",
    guide: {
      title: "커밋 메시지 형식 맞추기",
      summary: "type(scope): 설명 형식으로 커밋 메시지를 맞춘다",
      steps: [
        {
          instruction: "커밋 메시지를 형식에 맞게 다시 쓰세요.",
          hint: 'git commit -m "type(scope): 설명" (type: feat·fix·docs·test·chore·ci·refactor, scope: cli·watcher·web·db·infra·docs)',
        },
      ],
    },
  },
  {
    id: "R08",
    name: "PR 대상 브랜치 오류",
    severity: "low",
    target: "feature 브랜치 PR이 develop이 아니라 main을 대상으로 열림",
    detectedBy: "watcher (GitHub PR)",
    allowRun: null,
    // watcher 전용이라 CLI 경고 문장이 없다. 아래 두 줄과 복구 방법은 웹에서 쓴 임시 문장
    warning: "PR이 develop이 아니라 main을 대상으로 열렸어요.",
    consequence: "머지하면 develop을 거치지 않고 main에 바로 들어가요.",
    ifRun: "CLI 선택지가 없는 규칙이에요. watcher가 열린 PR의 base를 보고 GitHub에서 발견해 기록해요.",
    undo: "가능",
    recovery: "PR 화면 제목 옆 Edit을 눌러 base를 develop으로 바꿔요.",
    guide: null,
    draft: true,
  },
];

/** v0.2 로 미룬 규칙 (목록에만 흐리게 보여 준다) */
export const DEFERRED_RULES = [{ id: "R07", name: "되돌리기 어려운 명령", note: "v0.2" }];

export function ruleDoc(id: string | undefined): RuleDoc | undefined {
  return RULE_DOCS.find((r) => r.id === id);
}
