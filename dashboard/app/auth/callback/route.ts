// GitHub 로그인 후 Supabase 가 돌려보내는 주소.
// 받은 code 를 세션으로 바꿔 쿠키에 저장하고 원래 보던 화면으로 보낸다.
// 이 주소(http://localhost:3000/** , Vercel 주소)는 Supabase Auth 의 Redirect URLs 에 등록돼 있어야 한다.
import { NextResponse, type NextRequest } from "next/server";
import { safeNext } from "@/lib/safe-next";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get("code");
  const next = safeNext(searchParams.get("next"));

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(`${origin}${next}`);
  }
  return NextResponse.redirect(`${origin}/login?error=callback`);
}
