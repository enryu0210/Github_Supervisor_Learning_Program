/** 문장 안의 `명령어` 부분만 고정폭 글꼴로 보여 준다 */
export default function InlineCode({ text }: { text: string }) {
  return (
    <>
      {text.split(/(`[^`]+`)/).map((part, i) =>
        part.startsWith("`") && part.endsWith("`") ? (
          <code key={i} className="rounded bg-low-bg px-1.5 py-px font-mono text-[0.92em] text-text">
            {part.slice(1, -1)}
          </code>
        ) : (
          part
        ),
      )}
    </>
  );
}
