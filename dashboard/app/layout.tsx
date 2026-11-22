import type { Metadata } from "next";
import { Suspense } from "react";
import Nav from "@/components/Nav";
import UserMenu from "@/components/UserMenu";
import "./globals.css";

export const metadata: Metadata = {
  title: "Git Coach 대시보드",
  description: "팀 Git 협업 위반 기록과 복습 퀴즈를 보는 대시보드",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <Nav
          user={
            // 로그인 정보는 요청마다 달라서 Suspense 안에서 읽는다
            <Suspense fallback={<span className="inline-block h-[26px] w-[26px] rounded-full bg-accent-light" aria-hidden />}>
              <UserMenu />
            </Suspense>
          }
        />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-8 sm:py-7">{children}</main>
      </body>
    </html>
  );
}
