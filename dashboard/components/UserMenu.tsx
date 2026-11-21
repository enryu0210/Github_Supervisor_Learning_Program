import Link from "next/link";
import { signOut } from "@/lib/auth-actions";
import { USE_SUPABASE } from "@/lib/supabase/config";
import { getCurrentUser } from "@/lib/user";

/** 상단 오른쪽: 현재 사용자와 로그아웃 (Supabase 모드). 합성 데이터 모드는 이름만 */
export default async function UserMenu() {
  const user = await getCurrentUser();
  const avatar = <span className="inline-block h-[26px] w-[26px] rounded-full bg-accent-light" aria-hidden />;

  if (!user) {
    return USE_SUPABASE ? (
      <Link href="/login" className="font-semibold text-accent">
        로그인
      </Link>
    ) : null;
  }
  return (
    <>
      {avatar}
      <span>{user}</span>
      {USE_SUPABASE && (
        <form action={signOut}>
          <button type="submit" className="ml-1 rounded-md px-2 py-1 text-xs text-muted hover:bg-accent-soft hover:text-accent">
            로그아웃
          </button>
        </form>
      )}
    </>
  );
}
