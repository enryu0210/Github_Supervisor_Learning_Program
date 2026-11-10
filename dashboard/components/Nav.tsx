"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** 상단 메뉴. 순서와 이름은 docs/wireframes/README.md 기준 */
const MENU = [
  { href: "/", label: "개요" },
  { href: "/events", label: "위반 타임라인" },
  { href: "/me", label: "내 기록" },
  { href: "/quiz", label: "복습 퀴즈" },
  { href: "/rules", label: "규칙 도감" },
] as const;

// v0.1: 로그인 전까지 현재 사용자를 설정값 하나로 고정한다 (웹 가이드 3-3)
const CURRENT_USER = process.env.NEXT_PUBLIC_CURRENT_USER ?? "me";

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-6 border-b border-border bg-surface px-8 py-3.5">
      <Link href="/" className="mr-3 flex items-center gap-2 text-base font-bold">
        <span className="inline-block h-[22px] w-[22px] rounded-md bg-accent" aria-hidden />
        Git Coach
      </Link>
      {MENU.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={
              active
                ? "rounded-full bg-accent-soft px-3 py-1 font-bold text-accent"
                : "text-[#555] hover:text-accent"
            }
          >
            {item.label}
          </Link>
        );
      })}
      <span className="ml-auto flex items-center gap-2 text-sm text-[#555]">
        <span className="inline-block h-[26px] w-[26px] rounded-full bg-accent-light" aria-hidden />
        {CURRENT_USER}
      </span>
    </nav>
  );
}
