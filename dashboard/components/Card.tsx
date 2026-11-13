import type { ReactNode } from "react";

/** 흰 카드 + 제목. 오른쪽에 짧은 안내(hint)를 붙일 수 있다 */
export default function Card({
  title,
  hint,
  children,
  className = "",
}: {
  title: string;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-card bg-surface p-5 shadow-card ${className}`}>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[15px] font-bold">{title}</h2>
        {hint && <p className="text-xs text-muted">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

/** 카드 안 빈 상태 (작게) */
export function CardEmpty({ message }: { message: string }) {
  return <p className="py-6 text-center text-sm text-muted">{message}</p>;
}
