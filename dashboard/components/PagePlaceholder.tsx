/** 골격 단계의 빈 페이지. 각 화면을 구현하면 지운다. */
export default function PagePlaceholder({
  title,
  description,
  plan,
}: {
  title: string;
  description: string;
  plan: string;
}) {
  return (
    <section>
      <h1 className="text-[22px] font-bold">{title}</h1>
      <p className="mt-1.5 text-muted">{description}</p>
      <div className="mt-6 rounded-card bg-surface p-10 text-center shadow-card">
        <p className="text-3xl" aria-hidden>
          🛠️
        </p>
        <p className="mt-2 font-bold">아직 준비 중인 화면이에요</p>
        <p className="mt-1 text-sm text-muted">{plan}</p>
      </div>
    </section>
  );
}
