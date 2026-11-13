"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CURRENT_USER } from "@/lib/user";

/** 상단 메뉴. 순서와 이름은 docs/wireframes/README.md 기준 */
const MENU = [
  { href: "/", label: "개요" },
  { href: "/events", label: "위반 타임라인" },
  { href: "/me", label: "내 기록" },
  { href: "/quiz", label: "복습 퀴즈" },
  { href: "/rules", label: "규칙 도감" },
] as const;


export default function Nav() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-border bg-surface px-4 py-3.5 sm:px-8">
      <Link href="/" className="mr-3 flex items-center gap-2 text-base font-bold whitespace-nowrap">
        <span className="inline-block h-[22px] w-[22px] rounded-md bg-accent" aria-hidden />
        Git Coach
      </Link>
      {/* 좁은 화면에서는 메뉴가 둘째 줄로 내려가고 옆으로 밀어 볼 수 있다 */}
      <div className="order-last -mx-1 flex w-full gap-5 overflow-x-auto px-1 whitespace-nowrap md:order-none md:mx-0 md:w-auto md:gap-6 md:px-0">
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
                  : "py-1 text-[#555] hover:text-accent"
              }
            >
              {item.label}
            </Link>
          );
        })}
      </div>
      <span className="ml-auto flex items-center gap-2 text-sm text-[#555]">
        <span className="inline-block h-[26px] w-[26px] rounded-full bg-accent-light" aria-hidden />
        {CURRENT_USER}
      </span>
    </nav>
  );
}
