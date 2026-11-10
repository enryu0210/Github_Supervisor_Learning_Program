from gitcoach import context, events, explain, parser
from gitcoach.guide import matcher, state
from gitcoach.guide.scenarios import SCENARIOS
from gitcoach.models import (
    Context,
    Event,
    GuideAction,
    GuideOutcome,
    GuideState,
    Scenario,
    Violation,
    ViolationSnapshot,
)

_NO_GUIDE = "진행 중인 가이드가 없어요."


def start(
    violations: list[Violation],
    ctx: Context,
    guide_events: list[Event] | None = None,
    command_summary: str = "",
) -> GuideState:
    guide_events = guide_events or [None] * len(violations)
    queue = [
        ViolationSnapshot(
            rule_id=v.rule_id,
            severity=v.severity,
            branch=ctx.current_branch,
            guide_id=v.guide_id,
            facts=v.facts,
            title=v.title,
            event_id=ev.id if ev else None,
            command_summary=command_summary,
        )
        for v, ev in zip(violations, guide_events, strict=True)
    ]
    guide_state = GuideState(queue=queue, step_index=0, hint_count=0)
    state.save(guide_state)
    return guide_state


def start_message(guide_state: GuideState, command_summary: str) -> str:
    cancelled = f"   원래 명령({command_summary})은 취소했어요."
    return f"{cancelled}\n{_start_next(guide_state)}"


def current_prompt() -> str:
    guide_state = state.load()
    if guide_state is None:
        return _NO_GUIDE
    scenario = SCENARIOS[guide_state.queue[0].guide_id]
    step = scenario.steps[guide_state.step_index]
    return _format_step(scenario, guide_state, step)


def on_command(argv: list[str]) -> GuideOutcome:
    guide_state = state.load()
    if guide_state is None:
        return GuideOutcome(GuideAction.NONE)

    cmd = parser.parse(argv)
    scenario = SCENARIOS[guide_state.queue[0].guide_id]
    step = scenario.steps[guide_state.step_index]

    if matcher.is_check_command(cmd):
        return GuideOutcome(
            GuideAction.EXEC_AND_REMIND, _format_step(scenario, guide_state, step)
        )

    ctx = context.collect(cmd)
    snap = guide_state.queue[0]

    if not matcher.step_matches(step, cmd, ctx, snap):
        return GuideOutcome(
            GuideAction.FALLTHROUGH,
            f"가이드 진행 중: 다음은 — {step.instruction}",
        )

    return GuideOutcome(GuideAction.EXEC_AND_ADVANCE, _advance(guide_state, scenario))


def hint() -> str:
    guide_state = state.load()
    if guide_state is None:
        return _NO_GUIDE
    scenario = SCENARIOS[guide_state.queue[0].guide_id]
    step = scenario.steps[guide_state.step_index]
    guide_state.hint_count += 1
    state.save(guide_state)
    if guide_state.hint_count <= 1:
        return f"힌트: {step.hint}"
    return f"정답 예시: {step.answer}"


def done() -> str:
    guide_state = state.load()
    if guide_state is None:
        return _NO_GUIDE
    scenario = SCENARIOS[guide_state.queue[0].guide_id]
    return _advance(guide_state, scenario)


def skip() -> str:
    return _stop_current(advance_queue=True)


def stop() -> str:
    return _stop_current(advance_queue=False)


def _stop_current(*, advance_queue: bool) -> str:
    guide_state = state.load()
    if guide_state is None:
        return _NO_GUIDE
    snap = guide_state.queue[0]
    if snap.event_id is not None:
        events.record(
            events.make_event(
                rule_id=snap.rule_id,
                severity=snap.severity,
                branch=snap.branch,
                action="guide_stopped",
                command_summary=snap.command_summary,
                related_event_id=snap.event_id,
            )
        )

    if not advance_queue:
        state.clear()
        return "가이드를 중단했어요."

    guide_state.queue.pop(0)
    guide_state.step_index = 0
    guide_state.hint_count = 0
    if not guide_state.queue:
        state.clear()
        return "가이드를 중단했어요."

    state.save(guide_state)
    return f"이번 가이드는 건너뛰었어요.\n{_start_next(guide_state)}"


def _advance(guide_state: GuideState, scenario: Scenario) -> str:
    guide_state.hint_count = 0
    guide_state.step_index += 1

    if guide_state.step_index < len(scenario.steps):
        state.save(guide_state)
        step = scenario.steps[guide_state.step_index]
        return f"✅ 완료! {_format_step(scenario, guide_state, step)}"

    snap = guide_state.queue[0]
    if snap.event_id is not None:
        events.record(
            events.make_event(
                rule_id=snap.rule_id,
                severity=snap.severity,
                branch=snap.branch,
                action="guide_completed",
                command_summary=snap.command_summary,
                related_event_id=snap.event_id,
            )
        )
    summary = f"✅ 가이드 완료! 배운 점: {scenario.summary}"
    guide_state.queue.pop(0)
    guide_state.step_index = 0
    guide_state.hint_count = 0

    if not guide_state.queue:
        state.clear()
        return summary

    state.save(guide_state)
    return f"{summary}\n{_start_next(guide_state)}"


def _start_next(guide_state: GuideState) -> str:
    """큐의 맨 앞 가이드를 시작한다. explain()은 가이드가 실제로 시작되는 이
    시점에만 호출한다(다중 위반이어도 한꺼번에 미리 부르지 않음, 01_cli.md 3-6 5번)."""
    snap = guide_state.queue[0]
    scenario = SCENARIOS[snap.guide_id]
    step = scenario.steps[0]

    explanation = explain.explain(snap.rule_id, snap.title, snap.facts)
    if snap.event_id is not None:
        events.update_explanation(snap.event_id, explanation.text, explanation.llm_used)

    header = f"📘 가이드 시작: {scenario.title} (총 {len(scenario.steps)}단계)"
    return (
        f"💡 왜 문제일까요?\n   {explanation.text}\n\n"
        f"{header}\n{_format_step(scenario, guide_state, step)}"
    )


def _format_step(scenario: Scenario, guide_state: GuideState, step) -> str:
    position = guide_state.step_index + 1
    total = len(scenario.steps)
    return f"{position}/{total}  {step.instruction}\n     힌트: {step.hint}"
