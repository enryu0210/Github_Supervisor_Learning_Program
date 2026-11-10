import Link from "next/link";

/** 공통 빈 상태 */
export function EmptyState({ message, resetHref }: { message: string; resetHref?: string }) {
  return (
    <div className="rounded-card bg-surface p-8 text-center text-muted shadow-card">
      <p className="text-3xl" aria-hidden>
        🎉
      </p>
      <p className="mt-1 font-bold text-text">{message}</p>
      {resetHref && (
        <Link
          href={resetHref}
          className="mt-3 inline-block rounded-lg border border-accent px-4 py-1.5 text-sm font-semibold text-accent"
        >
          필터 초기화
        </Link>
      )}
    </div>
  );
}

/** 공통 로딩 (뼈대) */
export function LoadingState() {
  return (
    <div role="status" aria-label="불러오는 중" className="space-y-2.5">
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-xl bg-surface px-4 py-4 shadow-card">
          <div className="h-2.5 w-2/5 animate-pulse rounded bg-accent-light" />
          <div className="mt-2.5 h-2.5 w-4/5 animate-pulse rounded bg-accent-light/70" />
        </div>
      ))}
    </div>
  );
}
