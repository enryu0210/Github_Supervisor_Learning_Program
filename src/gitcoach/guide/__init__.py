from gitcoach import context, parser
from gitcoach.guide import matcher, state
from gitcoach.guide.scenarios import SCENARIOS
from gitcoach.models import (
    Context,
    GuideAction,
    GuideOutcome,
    GuideState,
    Scenario,
    Violation,
    ViolationSnapshot,
)

_NO_GUIDE = "진행 중인 가이드가 없어요."


def start(violations: list[Violation], ctx: Context) -> GuideState:
    queue = [
        ViolationSnapshot(
            rule_id=v.rule_id,
            severity=v.severity,
            branch=ctx.current_branch,
            guide_id=v.guide_id,
            facts=v.facts,
        )
        for v in violations
    ]
    guide_state = GuideState(queue=queue, step_index=0, hint_count=0)
    state.save(guide_state)
    return guide_state


def start_message(guide_state: GuideState, command_summary: str) -> str:
    scenario = SCENARIOS[guide_state.queue[0].guide_id]
    step = scenario.steps[0]
    header = f"📘 가이드 시작: {scenario.title} (총 {len(scenario.steps)}단계)"
    cancelled = f"   원래 명령({command_summary})은 취소했어요."
    return f"{header}\n{cancelled}\n{_format_step(scenario, guide_state, step)}"


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
    # TODO(cli-event-log): guide_stopped 기록 — guide_state.queue[0] 스냅샷 사용

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
    next_scenario = SCENARIOS[guide_state.queue[0].guide_id]
    next_step = next_scenario.steps[0]
    return (
        "이번 가이드는 건너뛰었어요. "
        f"다음 가이드를 시작해요: {next_scenario.title}\n"
        f"{_format_step(next_scenario, guide_state, next_step)}"
    )


def _advance(guide_state: GuideState, scenario: Scenario) -> str:
    guide_state.hint_count = 0
    guide_state.step_index += 1

    if guide_state.step_index < len(scenario.steps):
        state.save(guide_state)
        step = scenario.steps[guide_state.step_index]
        return f"✅ 완료! {_format_step(scenario, guide_state, step)}"

    # TODO(cli-event-log): guide_completed 기록 — guide_state.queue[0] 스냅샷 사용
    summary = f"✅ 가이드 완료! 배운 점: {scenario.summary}"
    guide_state.queue.pop(0)
    guide_state.step_index = 0
    guide_state.hint_count = 0

    if not guide_state.queue:
        state.clear()
        return summary

    state.save(guide_state)
    next_scenario = SCENARIOS[guide_state.queue[0].guide_id]
    next_step = next_scenario.steps[0]
    return (
        f"{summary}\n📘 가이드 시작: {next_scenario.title}\n"
        f"{_format_step(next_scenario, guide_state, next_step)}"
    )


def _format_step(scenario: Scenario, guide_state: GuideState, step) -> str:
    position = guide_state.step_index + 1
    total = len(scenario.steps)
    return f"{position}/{total}  {step.instruction}\n     힌트: {step.hint}"
