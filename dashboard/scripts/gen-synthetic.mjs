// 대시보드 화면을 채우기 위한 합성 데이터(3주치)를 만든다. 11/12 회의 결정:
//   "합성데이터로 이번 주 일요일까지 모든 컴포넌트를 채우고, 다음 주부터 실제 데이터 연동"
// - 레포 맨 위 samples/(CLI 계약용 20건)는 건드리지 않는다. 이 파일은 대시보드 전용이다.
// - 필드 이름: 이벤트 = 스키마 v1(01_cli.md 6절), PR·리뷰 = samples/watcher/, 퀴즈 = ERD quizzes
// - 고정 시드라 몇 번을 돌려도 같은 결과가 나온다.
// - 날짜는 ANCHOR_MONDAY 주를 "이번 주"로 두고 만든다. 화면에서는 mock 이 오늘이 속한 주로 옮겨서 보여 준다.
// 실행: cd dashboard && npm run synthetic:gen
import { createHash } from "node:crypto";
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ANCHOR_MONDAY = "2026-11-09"; // 이 날짜가 속한 주 = "이번 주"
const WEEKS = 3; // 이번 주 포함 3주 (10/26 ~ 11/15)
const REPO = "gitcoach-team/git-coach"; // samples/ 와 같은 레포
const MEMBERS = [
  { login: "jiyoon-lim", area: "web", rules: { R05: 3, R06: 3, R02: 1 } },
  { login: "ahyeon-kwon", area: "cli", rules: { R02: 2, R06: 1 } },
  { login: "namju-lee", area: "db", rules: { R06: 3, R04: 3, R03: 1 } },
  { login: "hoil-lim", area: "infra", rules: { R01: 3, R02: 2, R04: 1 } },
  { login: "ilho-jang", area: "infra", rules: { R01: 2, R05: 1, R06: 1 } },
];

// ---------------------------------------------------------------- 고정 난수
let seed = 20261112;
function rand() {
  seed |= 0;
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
const pick = (arr) => arr[Math.floor(rand() * arr.length)];
const chance = (p) => rand() < p;
const int = (lo, hi) => lo + Math.floor(rand() * (hi - lo + 1));
function weighted(obj) {
  const entries = Object.entries(obj);
  let r = rand() * entries.reduce((s, [, w]) => s + w, 0);
  for (const [k, w] of entries) if ((r -= w) < 0) return k;
  return entries[0][0];
}
function uuid4() {
  const h = Array.from({ length: 32 }, () => Math.floor(rand() * 16).toString(16)).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-${"89ab"[Math.floor(rand() * 4)]}${h.slice(17, 20)}-${h.slice(20, 32)}`;
}
/** watcher detected 용 uuid5 (01_cli.md 6절: name = rule_id \x1f repo \x1f entity) */
const NS = Buffer.from("6ba7b8109dad11d180b400c04fd430c8", "hex");
function uuid5(name) {
  const h = createHash("sha1").update(Buffer.concat([NS, Buffer.from(name)])).digest();
  h[6] = (h[6] & 0x0f) | 0x50;
  h[8] = (h[8] & 0x3f) | 0x80;
  const x = h.subarray(0, 16).toString("hex");
  return `${x.slice(0, 8)}-${x.slice(8, 12)}-${x.slice(12, 16)}-${x.slice(16, 20)}-${x.slice(20)}`;
}

// ---------------------------------------------------------------- 시간 (KST)
const DAY = 86400000;
const anchor = Date.parse(`${ANCHOR_MONDAY}T00:00:00+09:00`);
function iso(ms) {
  return new Date(ms + 9 * 3600000).toISOString().replace(/\.\d{3}Z$/, "+09:00");
}
const dayStart = (week, dow) => anchor + ((week - (WEEKS - 1)) * 7 + dow) * DAY; // week 0 = 가장 오래된 주
const at = (week, dow) => dayStart(week, dow) + int(10, 23) * 3600000 + int(0, 59) * 60000;
const plusMin = (ms, lo, hi) => ms + int(lo, hi) * 60000;

// ---------------------------------------------------------------- 규칙별 문장
// R01~R03 경고는 CLI 코드(rules/r0x_*.py), 나머지는 01_cli.md 3-3·3-4 초안을 바탕으로 한 합성 설명
const RULE = {
  R01: { severity: "high", explain: "main은 팀 전체가 공유하는 배포 브랜치예요. 리뷰·CI 없이 바로 올리면 배포까지 이어질 수 있어요.", done: "feature 브랜치로 옮겨 PR까지 올리는 가이드를 끝까지 완료함" },
  R02: { severity: "high", explain: "force push는 원격 기록을 내 기록으로 덮어써요. 같은 브랜치에 올린 다른 사람 커밋이 사라질 수 있어요.", done: "pull --rebase 후 일반 push로 올리는 가이드를 완료함" },
  R03: { severity: "high", explain: "비밀 정보가 담긴 파일이 staged 상태예요. 그대로 커밋하면 기록에 영구히 남아요." },
  R04: { severity: "medium", explain: "지금 main 위에서 바로 커밋하고 있어요. 다음 push에서 main 직접 push로 이어지고 원격과 갈라져요.", done: "feature 브랜치를 만들어 그 위에서 다시 커밋하는 가이드를 완료함" },
  R05: { severity: "low", explain: "브랜치명이 팀 규칙(feature|fix/영역-설명, 대문자·# 금지)과 달라요. 대시보드 영역별 통계에서 빠져요.", done: "제안 이름으로 브랜치를 다시 만드는 가이드를 완료함" },
  R06: { severity: "low", explain: "커밋 메시지가 팀 형식(type(scope): 설명)과 달라요. 나중에 기록을 읽기 어렵고 pr-convention CI가 실패해요.", done: "type(scope): 설명 형식으로 다시 커밋하는 가이드를 완료함" },
};
const STOP_REASON = ["guide stop으로 중단함", "guide skip으로 중단함", "두 번째 단계에서 guide stop으로 중단함"];

function featureBranch(m) {
  return `feature/${m.area}-${pick(["login", "chart", "filter", "schema", "poll", "config", "ci", "sync", "timeline"])}`;
}
function command(rule, m, branch) {
  switch (rule) {
    case "R01": return "git push origin main";
    case "R02": return chance(0.25) ? `git push --force-with-lease origin ${branch}` : `git push --force origin ${branch}`;
    case "R03": return pick(["git add .env", `git commit -m "feat(${m.area}): local config"`, "git add secrets/key.pem"]);
    case "R04": return `git commit -m "${pick([`fix(${m.area}): typo`, `feat(${m.area}): 설정 추가`, "wip"])}"`;
    case "R05": return `git switch -c ${pick(["MyBranch", "Feature/Login", "fix_bug", "test#1", "jiyoon-work"])}`;
    case "R06": return `git commit -m "${pick(["fix", "수정", "update", "asdf", "최종", "버그 고침"])}"`;
  }
}

const events = [];
const base = (m, rule, severity, branch, occurred) => ({
  id: uuid4(),
  schema_version: 1,
  occurred_at: iso(occurred),
  source: "cli",
  repo: REPO,
  member: m.login,
  rule_id: rule,
  severity,
  action: "allowed",
  command_summary: null,
  branch,
  pr_number: null,
  explanation: null,
  llm_used: false,
  related_event_id: null,
});

/** 가이드를 시작하고 결과(완료·중단·진행 중)를 남긴다. 결과 이벤트는 원래 값을 복사한다 (6절) */
// 가이드 결과는 주별 비율이 정확히 나오도록 난수 대신 고르게 퍼지는 수열(황금비)을 쓴다
const guideSeq = [0, 0, 0];
function guide(g, week, isLatest) {
  events.push(g);
  const completeP = [0.5, 0.65, 0.75][week]; // 주마다 완료율이 오른다
  const roll = (++guideSeq[week] * 0.6180339887 + week * 0.37) % 1;
  const t = Date.parse(g.occurred_at);
  if (roll < completeP) {
    events.push({ ...g, id: uuid4(), occurred_at: iso(plusMin(t, 3, 25)), action: "guide_completed", explanation: RULE[g.rule_id].done ?? "가이드를 완료함", llm_used: false, related_event_id: g.id });
  } else if (roll < completeP + 0.15 || !isLatest) {
    events.push({ ...g, id: uuid4(), occurred_at: iso(plusMin(t, 2, 15)), action: "guide_stopped", explanation: pick(STOP_REASON), llm_used: false, related_event_id: g.id });
  } // 나머지: 이번 주 마지막 날 가까이에서 시작해 아직 진행 중
}

// ---------------------------------------------------------------- CLI 이벤트
for (let week = 0; week < WEEKS; week++) {
  const perDay = [1.5, 1.1, 0.75][week]; // 주마다 위반이 줄어든다 (학습 효과)
  const guidedP = [0.55, 0.68, 0.78][week]; // [2] 가이드를 고르는 비율은 늘어난다
  for (let dow = 0; dow < 7; dow++) {
    for (const m of MEMBERS) {
      const lambda = perDay * (dow >= 5 ? 0.35 : 1) * (m.login === "ahyeon-kwon" ? 0.5 : 1);
      let n = 0;
      for (let k = 0; k < 4; k++) if (chance(lambda / 4)) n++;
      for (let i = 0; i < n; i++) {
        const t = at(week, dow);
        const isLatest = week === WEEKS - 1 && dow >= 3;
        const rule = chance(0.05) ? "R03" : weighted(m.rules);
        const branch = rule === "R01" || rule === "R04" ? "main" : rule === "R05" ? null : featureBranch(m);
        const cmd = command(rule, m, branch ?? "");
        const sev = rule === "R02" && cmd.includes("--force-with-lease") ? "medium" : RULE[rule].severity;
        const b = { ...base(m, rule, sev, branch ?? cmd.split(" ").pop(), t), command_summary: cmd };

        if (rule === "R03") {
          // R03은 [1]이 없다. [q] → blocked 1건, [2] → 가이드
          if (chance(0.5)) events.push({ ...b, action: "blocked", explanation: RULE.R03.explain });
          else guide({ ...b, action: "guided", explanation: RULE.R03.explain, llm_used: chance(0.7) }, week, isLatest);
          continue;
        }
        if (chance(guidedP)) {
          guide({ ...b, action: "guided", explanation: RULE[rule].explain, llm_used: chance(0.7) }, week, isLatest);
        } else {
          events.push(b); // allowed: 설명 null, llm_used false
          // 그냥 실행한 force push 를 나중에 guide undo 로 되돌림 (복구 가이드)
          if (rule === "R02" && chance(0.4)) {
            guide({ ...b, id: uuid4(), occurred_at: iso(plusMin(t, 5, 40)), action: "guided", command_summary: "gitcoach guide undo", explanation: "아까 그냥 실행한 force push를 되돌리는 복구 가이드예요.", llm_used: chance(0.7), related_event_id: b.id }, week, isLatest);
          }
        }
      }
    }
  }
  // 다중 위반: 한 명령에 R01·R02 (위반마다 1건, 같은 command_summary)
  const m = pick(MEMBERS);
  const t = at(week, int(0, 4));
  for (const rule of ["R01", "R02"]) {
    guide({ ...base(m, rule, "high", "main", t), command_summary: "git push --force origin main", action: "guided", explanation: RULE[rule].explain, llm_used: true }, week, false);
  }
}

// ---------------------------------------------------------------- PR · 리뷰 (samples/watcher 형식)
const PR_TITLES = {
  web: ["feat(web): 개요 KPI 카드", "feat(web): 규칙별 위반 차트", "fix(web): 필터 칩 정렬", "feat(web): /me 진행 막대", "feat(web): 퀴즈 화면"],
  cli: ["feat(cli): R05 브랜치명 규칙", "fix(cli): 파서 짧은 플래그", "feat(cli): gitcoach sync", "docs(cli): 가이드 시나리오 표"],
  db: ["feat(db): events 마이그레이션", "feat(db): v_stale_prs 뷰", "fix(db): RLS 정책 수정", "feat(db): get_rule_stats RPC"],
  infra: ["ci(infra): web lint 잡 추가", "chore(infra): compose 정리", "feat(infra): Vercel 프리뷰", "ci(infra): secret-scan 재시도"],
};
const prs = [];
const reviews = [];
let prNo = 101;
let reviewNo = 5002000001;
for (let week = 0; week < WEEKS; week++) {
  const count = [7, 8, 7][week];
  for (let i = 0; i < count; i++) {
    const author = pick(MEMBERS);
    const others = MEMBERS.filter((m) => m !== author);
    const reviewers = chance(0.45) ? [pick(others), pick(others)].filter((v, j, a) => a.indexOf(v) === j) : [pick(others)];
    const dow = int(0, week === WEEKS - 1 ? 3 : 5);
    const opened = at(week, dow);
    // 방치 PR: 지난주에 열고 활동이 멈춘 것 2개 + 이번 주 월요일에 열고 멈춘 것 1개
    const stale = (week === WEEKS - 2 && i < 2) || (week === WEEKS - 1 && i === 0);
    const merged = !stale && (week < WEEKS - 1 ? chance(0.9) : chance(0.55));
    const mergedAt = merged ? plusMin(opened, 6 * 60, 40 * 60) : null;
    const pr = {
      repo: REPO,
      number: prNo++,
      title: pick(PR_TITLES[author.area]),
      author: author.login,
      state: merged ? "closed" : "open",
      opened_at: iso(opened),
      merged_at: mergedAt ? iso(mergedAt) : null,
      reviewers: reviewers.map((r) => r.login),
      last_activity_at: iso(mergedAt ?? (stale ? plusMin(opened, 20, 120) : plusMin(opened, 60, 20 * 60))),
      base: chance(0.08) ? "main" : "develop", // R08 감지용 (watcher 가 보는 값, DB prs 컬럼 아님)
    };
    prs.push(pr);

    const end = Date.parse(pr.last_activity_at);
    for (const r of reviewers) {
      if (stale && chance(0.6)) continue; // 방치 PR은 리뷰가 없거나 적다
      const first = opened + (end - opened) * (0.2 + rand() * 0.3);
      const add = (status, t) =>
        reviews.push({ review_id: reviewNo, repo: REPO, pr_number: pr.number, reviewer: r.login, status, submitted_at: iso(t), commit_sha: createHash("sha1").update(String(reviewNo)).digest("hex"), html_url: `https://github.com/${REPO}/pull/${pr.number}#pullrequestreview-${reviewNo++}` });
      if (chance(0.45)) add("COMMENTED", first); // 같은 PR에 여러 번 리뷰 (1로 세야 함)
      if (merged || chance(0.5)) add(chance(0.12) ? "DISMISSED" : "APPROVED", Math.min(end, first + (end - first) * 0.7));
    }
    // 작성자가 리뷰 스레드에 답글 → 리뷰로 기록될 수 있음 (세면 안 됨)
    if (chance(0.15)) reviews.push({ review_id: reviewNo, repo: REPO, pr_number: pr.number, reviewer: author.login, status: "COMMENTED", submitted_at: pr.last_activity_at, commit_sha: createHash("sha1").update(String(reviewNo)).digest("hex"), html_url: `https://github.com/${REPO}/pull/${pr.number}#pullrequestreview-${reviewNo++}` });
  }
}

// ---------------------------------------------------------------- watcher detected (source = github, uuid5)
// 같은 대상(브랜치·커밋·PR)은 uuid5 가 같아 watcher 가 한 번만 저장한다 → 이미 있으면 건너뛴다
const detected = (m, rule, entity, t, extra) => {
  const id = uuid5(`${rule}\x1f${REPO}\x1f${entity}`);
  if (events.some((e) => e.id === id)) return;
  events.push({ ...base(m, rule, RULE[rule]?.severity ?? "low", null, t), id, source: "github", action: "detected", ...extra });
};
for (const pr of prs) {
  const m = MEMBERS.find((x) => x.login === pr.author);
  const t = plusMin(Date.parse(pr.opened_at), 1, 10);
  if (pr.base === "main") detected(m, "R08", `pr:${pr.number}`, t, { severity: "low", branch: featureBranch(m), pr_number: pr.number, explanation: `PR #${pr.number}이 develop이 아니라 main을 대상으로 열렸어요.` });
  if (chance(0.22)) detected(m, "R06", createHash("sha1").update(`c${pr.number}`).digest("hex"), t, { branch: featureBranch(m), pr_number: pr.number, explanation: `PR #${pr.number}의 커밋 목록 조회 결과 커밋 메시지 규칙 위반 발견` });
  if (chance(0.12)) { const br = pick(["Feature_Login", "hotfix-ui", "Fix/DB"]); detected(m, "R05", br, t, { branch: br, explanation: "GitHub 브랜치 목록 조회 결과 브랜치명 규칙 위반 발견" }); }
}
for (let week = 0; week < WEEKS; week++) {
  const m = pick(MEMBERS); // IDE Git 버튼으로 main 에 push (CLI 를 거치지 않음)
  detected(m, "R01", createHash("sha1").update(`h${week}`).digest("hex"), at(week, int(0, 4)), { branch: "main", explanation: "IDE Git 버튼 등 CLI를 거치지 않은 main 직접 push가 감지됐어요." });
}

// ---------------------------------------------------------------- 퀴즈 (watcher 가 출제, 근거 = allowed·guide_stopped)
const BANK = {
  R01: [["main에 직접 push하면 생길 수 있는 일은?", ["리뷰·CI 없이 배포까지 이어질 수 있다", "push가 자동으로 PR로 바뀐다", "로컬 커밋이 사라진다", "아무 일도 없다"], 0, "main은 팀이 공유하는 배포 브랜치라 리뷰·CI를 거쳐 PR로 들어가야 해요."]],
  R02: [["팀원이 이미 push한 브랜치에 git push -f를 하면?", ["아무 일도 없다", "팀원의 커밋이 원격에서 사라질 수 있다", "내 로컬 커밋이 삭제된다", "PR이 자동 병합된다"], 1, "force push는 원격 기록을 내 기록으로 덮어써요."], ["force push 대신 먼저 해야 하는 것은?", ["git pull --rebase", "git reset --hard", "git clean -fd", "git branch -D"], 0, "원격 변경을 먼저 가져와 맞춘 뒤 일반 push로 올려요."]],
  R03: [[".env를 실수로 staged 했을 때 올바른 명령은?", ["git restore --staged .env", "git commit --amend", "git push --force", "git add ."], 0, "staged에서 빼고 .gitignore에 등록해요."]],
  R04: [["main에서 커밋해 버렸을 때 먼저 할 일은?", ["feature 브랜치를 만들어 커밋을 옮긴다", "바로 push한다", "레포를 지우고 다시 clone한다", "git clean -fd"], 0, "git branch feature/...로 커밋을 옮긴 뒤 main을 원격 상태로 되돌려요."]],
  R05: [["팀 규칙에 맞는 브랜치 이름은?", ["Feature/Login", "feature/web-login", "fix_bug", "test#1"], 1, "feature|fix/<영역>-<설명>, 소문자만 써요."]],
  R06: [["팀 규칙에 맞는 커밋 메시지는?", ["수정", "fix", "feat(web): 개요 KPI 카드 추가", "asdf"], 2, "type(scope): 설명 형식이에요."], ["push 전에 커밋 메시지를 고치는 명령은?", ["git commit --amend", "git push -f", "git reset --hard", "git revert"], 0, "push 전이라면 --amend로 고칠 수 있어요. push 후 amend는 force push가 필요해요."]],
};
const quizzes = [];
for (const m of MEMBERS) {
  const basis = events
    .filter((e) => e.member === m.login && e.source === "cli" && (e.action === "allowed" || e.action === "guide_stopped") && BANK[e.rule_id])
    .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at))
    .slice(0, 4);
  for (const e of basis) {
    const [question, choices, answer_index, explanation] = pick(BANK[e.rule_id]);
    quizzes.push({ id: uuid4(), member: m.login, rule_id: e.rule_id, source_event_id: e.id, question, choices, answer_index, explanation, created_at: iso(plusMin(Date.parse(e.occurred_at), 10, 60)) });
  }
}

events.sort((a, b) => a.occurred_at.localeCompare(b.occurred_at));
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "lib", "data", "mock", "synthetic.json");
const data = { anchor_monday: ANCHOR_MONDAY, members: MEMBERS.map((m) => m.login), events, prs: prs.map((p) => { const copy = { ...p }; delete copy.base; return copy; }), pr_reviews: reviews, quizzes };
writeFileSync(out, JSON.stringify(data, null, 1) + "\n");
console.log(`synthetic → ${out}\n  events ${events.length} · prs ${prs.length} · pr_reviews ${reviews.length} · quizzes ${quizzes.length}`);
