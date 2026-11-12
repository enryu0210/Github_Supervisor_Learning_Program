// v0.1: 로그인 전까지 현재 사용자를 설정값 하나로 고정한다 (웹 가이드 3-3)
// .env.local 의 NEXT_PUBLIC_CURRENT_USER 로 바꿀 수 있다. 11/19~20 GitHub 로그인으로 교체한다.
// 서버 컴포넌트(/me, /quiz)와 Nav(클라이언트)가 함께 쓰므로 "use client" 파일이 아닌 여기에 둔다.
export const CURRENT_USER = process.env.NEXT_PUBLIC_CURRENT_USER ?? "jiyoon-lim";
