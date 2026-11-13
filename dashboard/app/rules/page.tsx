import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import Badge from "@/components/Badge";
import Card from "@/components/Card";
import InlineCode from "@/components/InlineCode";
import { LoadingState } from "@/components/StateViews";
import { data } from "@/lib/data";
import type { SearchParams } from "@/lib/filters";
import { severityLabel } from "@/lib/labels";
import { DEFERRED_RULES, RULE_DOCS, ruleDoc, type RuleDoc } from "@/lib/rules";
import { thisWeekRange } from "@/lib/time";
import { CURRENT_USER } from "@/lib/user";

// /rules 규칙 도감 (와이어프레임 05-rules)
// 왼쪽 목록 + 오른쪽 상세. 선택한 규칙은 ?rule=R01 로 URL 에 둔다 (/me 의 "규칙 도감 보기"가 이 주소로 온다)

export default function RulesPage({ searchParams }: PageProps<"/rules">) {
  return (
    <section>
      <h1 className="sr-only">규칙 도감</h1>
      <Suspense fallback={<LoadingState />}>
        <RulesContent searchParams={searchParams} />
      </Suspense>
    </section>
  );
}

async function RulesContent({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const rule = ruleDoc(typeof sp.rule === "string" ? sp.rule : undefined) ?? RULE_DOCS[0];

  return (
    <div className="grid gap-6 md:grid-cols-[260px_minmax(0,1fr)]">
      {/* ---------------- 규칙 목록 ---------------- */}
      <nav aria-label="규칙 목록" className="h-fit rounded-card bg-surface p-4 shadow-card">
        <h2 className="mb-3 px-2 text-[15px] font-bold">규칙 목록</h2>
        <ul className="space-y-1">
          {RULE_DOCS.map((r) => {
            const active = r.id === rule.id;
            return (
              <li key={r.id}>
                <Link
                  href={`/rules?rule=${r.id}`}
                  scroll={false}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center justify-between gap-2 rounded-xl px-3 py-2.5 text-[13px] ${
                    active ? "bg-accent font-semibold text-white" : "hover:bg-accent-soft"
                  }`}
                >
                  <span className="truncate">
                    {r.id} {r.name}
                  </span>
                  {active ? (
                    <span className="shrink-0 text-[11px]">{severityLabel(r.severity).label}</span>
                  ) : (
                    <Badge info={severityLabel(r.severity)} />
                  )}
                </Link>
              </li>
            );
          })}
          {DEFERRED_RULES.map((r) => (
            <li key={r.id} className="flex justify-between px-3 py-2.5 text-[13px] text-muted/70" title="v0.2에서 추가할 규칙">
              <span>
                {r.id} {r.name}
              </span>
              <span>{r.note}</span>
            </li>
          ))}
        </ul>
      </nav>

      {/* ---------------- 상세 ---------------- */}
      <article className="min-w-0">
        <div className="flex flex-wrap gap-1.5">
          <Badge info={severityLabel(rule.severity)} />
          {rule.allowRun === true && <Badge info={{ label: "그냥 실행 가능", description: "", tone: "success" }} />}
          {rule.allowRun === false && <Badge info={{ label: "그냥 실행 불가", description: "", tone: "danger" }} />}
          {rule.allowRun === null && <Badge info={{ label: "GitHub에서만 감지", description: "", tone: "notice" }} />}
          <Badge text={`감지: ${rule.detectedBy}`} />
        </div>
        <h2 className="mt-3 text-[24px] font-bold">
          {rule.id} · {rule.name}
        </h2>
        <p className="mt-1 text-muted">{rule.target}</p>

        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <Card title="⚠️ 왜 위험한가요?">
            <p className="text-sm leading-relaxed">
              <InlineCode text={rule.warning} />
            </p>
            <p className="mt-2 text-sm leading-relaxed text-muted">{rule.consequence}</p>
            {rule.allowRun !== null && <p className="mt-3 text-[11px] text-muted">CLI 경고 화면과 같은 문장이에요.</p>}
          </Card>
          <Card title={rule.allowRun === null ? "▶ 어떻게 잡히나요?" : "▶ 그냥 실행하면"} hint={rule.undo !== "—" ? <UndoBadge undo={rule.undo} /> : undefined}>
            <p className="text-sm leading-relaxed">{rule.ifRun}</p>
          </Card>
        </div>

        <GuideCard rule={rule} />

        <Card title="🔧 이미 실행했다면" className="mt-5">
          <p className="text-sm leading-relaxed">
            {rule.recovery === "—" ? "그냥 실행할 수 없는 규칙이라 사후 복구가 필요 없어요." : <InlineCode text={rule.recovery} />}
          </p>
        </Card>

        <Suspense fallback={<div className="mt-5"><LoadingState /></div>}>
          <TeamAndQuiz ruleId={rule.id} />
        </Suspense>

        {rule.draft && (
          <p className="mt-4 text-[11px] text-muted">
            ※ 이 규칙은 watcher 전용이라 CLI 경고 문장이 없어요. 경고·복구 문장은 웹에서 임시로 쓴 초안이에요.
          </p>
        )}
      </article>
    </div>
  );
}

function UndoBadge({ undo }: { undo: string }) {
  const tone = undo.startsWith("가능") || undo === "쉬움" || undo.includes("쉬움") ? "success" : "warning";
  return <Badge info={{ label: `되돌리기 ${undo}`, description: "", tone }} />;
}

function GuideCard({ rule }: { rule: RuleDoc }) {
  if (!rule.guide) {
    return (
      <Card title="📘 올바른 방법" className="mt-5">
        <p className="text-sm leading-relaxed">
          feature 브랜치의 PR은 <InlineCode text="`develop`" />을 base로 열어요. CLI 가이드가 없는 규칙이라 GitHub PR 화면에서 직접 고쳐요.
        </p>
      </Card>
    );
  }
  return (
    <Card title="📘 올바른 방법" hint={`가이드 ${rule.guide.steps.length}단계 · ${rule.guide.title}`} className="mt-5">
      <ol className="space-y-2.5">
        {rule.guide.steps.map((s, i) => (
          <li key={i} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl bg-bg px-4 py-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-[13px] font-bold text-white">
              {i + 1}
            </span>
            <span className="text-sm">{s.instruction}</span>
            <code className="rounded bg-surface px-2 py-0.5 font-mono text-xs break-all">{s.hint}</code>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-[11px] text-muted">CLI에서 [2] 어떻게 해야 하나요?를 고르면 이 순서대로 직접 입력하며 따라 해요.</p>
    </Card>
  );
}

/** 아래 두 칸: 우리 팀 이번 주 숫자, 내 관련 퀴즈 */
async function TeamAndQuiz({ ruleId }: { ruleId: string }) {
  await connection(); // "이번 주"는 요청 시각 기준
  const week = { range: thisWeekRange(), ruleIds: [ruleId] };
  const [stats, guides, quizzes] = await Promise.all([
    data.getRuleStats(week),
    data.getGuideStats(week),
    data.getQuizzes(CURRENT_USER),
  ]);
  const count = stats[0]?.violation_count ?? 0;
  const g = guides[0];
  const mine = quizzes.filter((q) => q.rule_id === ruleId).length;

  return (
    <div className="mt-5 grid gap-5 sm:grid-cols-2">
      <Card title="우리 팀 이번 주">
        <p className="text-[30px] leading-none font-bold">
          {count}
          <span className="ml-0.5 text-lg">건</span>
        </p>
        <p className="mt-2 text-xs text-muted">
          {g?.guided_count ? `가이드 완료율 ${Math.round(g.completion_rate * 100)}% (${g.completed_count}/${g.guided_count})` : "이번 주 시작한 가이드 없음"}
        </p>
        <Link href={`/events?rule=${ruleId}&period=week`} className="mt-3 inline-block text-[13px] font-semibold text-accent">
          타임라인에서 보기 →
        </Link>
      </Card>
      <Card title="관련 퀴즈">
        {mine > 0 ? (
          <>
            <p className="text-sm text-muted">내 복습 문제 중 {ruleId} 문제가 {mine}개 있어요.</p>
            <Link
              href={`/quiz?rule=${ruleId}`}
              className="mt-3 inline-block rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white"
            >
              {ruleId} 문제 풀기 →
            </Link>
          </>
        ) : (
          <p className="text-sm text-muted">아직 이 규칙으로 나온 내 복습 문제가 없어요.</p>
        )}
      </Card>
    </div>
  );
}
