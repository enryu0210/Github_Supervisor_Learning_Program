import Link from "next/link";
import { Suspense } from "react";
import type { SearchParams } from "@/lib/filters";
import { signInWithGitHub } from "@/lib/auth-actions";
import { USE_SUPABASE } from "@/lib/supabase/config";

const ERRORS: Record<string, string> = {
  start: "GitHub 로그인을 시작하지 못했어요. 잠시 뒤 다시 시도해 주세요.",
  callback: "로그인을 마치지 못했어요. 다시 시도해 주세요.",
};

export default function LoginPage({ searchParams }: PageProps<"/login">) {
  return (
    <section className="mx-auto mt-10 max-w-md rounded-card bg-surface p-8 text-center shadow-card">
      <span className="mx-auto block h-11 w-11 rounded-xl bg-accent" aria-hidden />
      <h1 className="mt-4 text-[22px] font-bold">Git Coach 대시보드</h1>
      <p className="mt-2 text-sm text-muted">팀 GitHub 계정으로 로그인하면 우리 팀 기록과 내 복습 문제를 볼 수 있어요.</p>
      <Suspense fallback={null}>
        <LoginForm searchParams={searchParams} />
      </Suspense>
    </section>
  );
}

async function LoginForm({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  if (!USE_SUPABASE) {
    return (
      <p className="mt-6 text-sm">
        지금은 합성 데이터 모드라 로그인 없이 볼 수 있어요.{" "}
        <Link href="/" className="font-semibold text-accent">
          개요로 가기 →
        </Link>
      </p>
    );
  }
  const error = typeof sp.error === "string" ? ERRORS[sp.error] : undefined;
  const next = typeof sp.next === "string" ? sp.next : "/";
  return (
    <>
      {error && (
        <p role="alert" className="mt-5 rounded-lg bg-high-bg px-3 py-2 text-sm text-high">
          {error}
        </p>
      )}
      <form action={signInWithGitHub} className="mt-6">
        <input type="hidden" name="next" value={next} />
        <button
          type="submit"
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#1d1f2c] px-4 py-3 text-sm font-semibold text-white hover:opacity-90"
        >
          <svg aria-hidden viewBox="0 0 16 16" className="h-4 w-4 fill-current">
            <path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38v-1.33c-2.23.48-2.7-1.07-2.7-1.07-.36-.92-.89-1.17-.89-1.17-.73-.5.06-.49.06-.49.8.06 1.23.83 1.23.83.72 1.22 1.87.87 2.33.66.07-.52.28-.87.5-1.07-1.78-.2-3.65-.89-3.65-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.2c0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
          </svg>
          GitHub로 로그인
        </button>
      </form>
      <p className="mt-4 text-[11px] leading-relaxed text-muted">
        팀 멤버로 등록된 계정만 데이터가 보여요. 처음 로그인하면 GitHub 계정이 팀 멤버에 자동으로 연결돼요.
      </p>
    </>
  );
}
