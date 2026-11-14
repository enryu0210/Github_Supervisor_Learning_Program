import { connection } from "next/server";
import { Suspense } from "react";
import FilterRow from "@/components/FilterRow";
import QuizRunner, { type QuizItem } from "@/components/QuizRunner";
import { EmptyState, LoadingState } from "@/components/StateViews";
import { data } from "@/lib/data";
import type { SearchParams } from "@/lib/filters";
import { CURRENT_USER } from "@/lib/user";

// /quiz 복습 퀴즈 (와이어프레임 04-quiz)
// - 퀴즈는 웹에서 만들지 않는다. watcher 가 만들어 DB 에 넣은 것을 보여 주기만 한다
// - v0.1 은 풀이를 저장하지 않는다 (D5). 정답·해설은 고른 즉시 화면에서만 보여 준다
// - ?rule=R02 로 규칙을 고를 수 있다 (/rules 의 "문제 풀기"가 이 주소로 온다)

export default function QuizPage({ searchParams }: PageProps<"/quiz">) {
  return (
    <section>
      <h1 className="text-[22px] font-bold">복습 퀴즈</h1>
      <p className="mt-1.5 mb-4 text-muted">내가 그냥 실행했거나 가이드를 멈춘 기록으로 만든 문제예요.</p>
      <Suspense fallback={<LoadingState />}>
        <QuizContent searchParams={searchParams} />
      </Suspense>
    </section>
  );
}

async function QuizContent({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  await connection();
  const all = await data.getQuizzes(CURRENT_USER);
  const rule = typeof sp.rule === "string" ? sp.rule : undefined;
  const quizzes = rule ? all.filter((q) => q.rule_id === rule) : all;

  // 문제마다 "이 문제가 나온 이유" 이벤트를 붙인다
  const events = await data.getEvents({ members: [CURRENT_USER] });
  const byId = new Map(events.map((e) => [e.id, e]));
  const items: QuizItem[] = quizzes.map((q) => ({
    quiz: q,
    source: q.source_event_id ? (byId.get(q.source_event_id) ?? null) : null,
  }));
  const rules = [...new Set(all.map((q) => q.rule_id))].sort();

  return (
    <>
      {rules.length > 1 && (
        <div className="mb-4 rounded-card bg-surface px-4 pt-3 pb-1.5 shadow-card">
          <FilterRow
            label="규칙"
            all={{ label: `전체 ${all.length}`, href: "/quiz", active: !rule }}
            chips={rules.map((r) => ({
              label: `${r} ${all.filter((q) => q.rule_id === r).length}`,
              href: `/quiz?rule=${r}`,
              active: rule === r,
            }))}
          />
        </div>
      )}
      {items.length === 0 ? (
        <EmptyState message="지금은 풀 문제가 없어요" resetHref={rule ? "/quiz" : undefined} />
      ) : (
        // 규칙을 바꾸면 처음부터 다시 풀도록 key 를 준다
        <QuizRunner key={rule ?? "all"} items={items} />
      )}
    </>
  );
}
