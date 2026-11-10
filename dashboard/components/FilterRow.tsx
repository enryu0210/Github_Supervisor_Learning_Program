import Link from "next/link";

export type Chip = { label: string; href: string; active: boolean };

/** 필터 한 줄. "전체" + 선택지 칩. 칩은 링크라서 JS 없이도 동작하고, 상태는 URL에만 남는다. */
export default function FilterRow({ label, all, chips }: { label: string; all: Chip; chips: Chip[] }) {
  return (
    <div className="flex flex-wrap items-center">
      <span className="w-14 pb-1.5 text-xs text-muted">{label}</span>
      {[all, ...chips].map((c) => (
        <Link
          key={c.label}
          href={c.href}
          scroll={false}
          aria-pressed={c.active}
          className={`mr-1.5 mb-1.5 rounded-full border px-3 py-1 text-xs ${
            c.active
              ? "border-accent bg-accent font-semibold text-white"
              : "border-border bg-surface hover:border-accent"
          }`}
        >
          {c.label}
        </Link>
      ))}
    </div>
  );
}
