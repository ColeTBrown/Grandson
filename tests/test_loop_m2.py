"""M2 control-loop tests: bounds, safe-stop, scam-fire, verify, no-bypass.

No real hardware, screen, or network: every collaborator is injected. We prove
the loop's *policy* — the parts the architect made non-negotiable (M2-PLAN
§3/§4) — and the structural no-bypass property of the actor.

    PYTHONPATH=src python -m unittest tests.test_loop_m2 -v
"""

import unittest

from grandson import loop, actor
from grandson.actor import Action, ActionKind, ActionOutcome
from grandson.planner import PlanResult
from grandson import safety


# --- Fakes -----------------------------------------------------------------

def _plan(kind=ActionKind.CLICK_ELEMENT, desc="click Accessibility",
          target="Accessibility", confident=True, reason=""):
    return PlanResult(
        action=Action(kind=kind, human_description=desc, target=target),
        confident=confident, reason=reason,
    )


def _done_plan():
    return PlanResult(action=Action(ActionKind.DONE, ""), confident=True)


class Recorder:
    """Collects everything the loop says, for assertions."""

    def __init__(self):
        self.lines = []

    def __call__(self, msg):
        self.lines.append(msg)

    @property
    def text(self):
        return "\n".join(self.lines).lower()


def _run(**overrides):
    """Run the loop with safe no-op defaults, overridable per test."""
    say = overrides.pop("say", Recorder())
    defaults = dict(
        client=None,
        config=loop.LoopConfig(step_budget=12, time_cap_seconds=999, pace_seconds=0),
        say=say,
        read_input=lambda _p: "",
        should_stop=lambda: False,
        pause=lambda _s: None,
        capture=lambda: b"img",
        describe=lambda _c, _i: "a normal System Settings screen",
        propose=lambda _c, _d: _done_plan(),
        execute=lambda a, **k: ActionOutcome(
            performed=True, allowed=True,
            decision=safety.ActionDecision(safety.Risk.ROUTINE),
        ),
    )
    defaults.update(overrides)
    code = loop.run_task(defaults.pop("client"), defaults.pop("config"), **defaults)
    return code, say


# --- No-bypass: structural proof -------------------------------------------

class NoBypass(unittest.TestCase):
    """The ONLY path to the hardware primitive is through the gate."""

    def test_gated_execute_does_not_perform_when_gate_refuses(self):
        calls = []

        def fake_perform(_action):
            calls.append("perform")

        # Patch the private primitive; force the gate to refuse (RISKY, no yes).
        orig = actor._perform
        actor._perform = fake_perform
        try:
            out = actor.gated_execute(
                Action(ActionKind.CLICK_ELEMENT, "Open Privacy & Security",
                       "Privacy & Security"),
                read_input=lambda _p: "",  # not a yes
                write_output=lambda _m: None,
            )
        finally:
            actor._perform = orig

        self.assertFalse(out.performed)
        self.assertFalse(out.allowed)
        self.assertEqual(calls, [])  # hardware NEVER touched on a refusal.

    def test_gated_execute_performs_only_after_allow(self):
        calls = []
        orig = actor._perform
        actor._perform = lambda a: calls.append(a.kind)
        try:
            out = actor.gated_execute(
                Action(ActionKind.OPEN_APP, "Open System Settings", "System Settings"),
                read_input=lambda _p: "", write_output=lambda _m: None,
            )
        finally:
            actor._perform = orig
        self.assertTrue(out.performed)
        self.assertEqual(calls, [ActionKind.OPEN_APP])

    def test_blocked_never_performs_even_with_yes(self):
        calls = []
        orig = actor._perform
        actor._perform = lambda a: calls.append(a)
        try:
            out = actor.gated_execute(
                Action(ActionKind.CLICK_ELEMENT, "Type the admin password", "x"),
                read_input=lambda _p: "yes", write_output=lambda _m: None,
            )
        finally:
            actor._perform = orig
        self.assertFalse(out.performed)
        self.assertEqual(out.decision.risk, safety.Risk.BLOCKED)
        self.assertEqual(calls, [])


# --- Gate sees the structured target, not just the narration (Fix 1) -------

class GateCoversStructuredAction(unittest.TestCase):
    """A benign description can't smuggle a risky target past the gate."""

    def test_benign_description_risky_target_does_not_perform(self):
        # Description reads harmless; the TARGET is the dangerous pane. The old
        # code gated only the description and would have performed this.
        calls = []
        orig = actor._perform
        actor._perform = lambda a: calls.append(a)
        try:
            out = actor.gated_execute(
                Action(
                    ActionKind.CLICK_ELEMENT,
                    "open the screen where text size lives",
                    "Privacy & Security",
                ),
                read_input=lambda _p: "",  # not a yes
                write_output=lambda _m: None,
            )
        finally:
            actor._perform = orig
        self.assertFalse(out.performed)
        self.assertFalse(out.allowed)
        self.assertEqual(out.decision.risk, safety.Risk.RISKY)
        self.assertEqual(calls, [])  # hardware NEVER touched.

    def test_benign_description_credential_target_is_blocked(self):
        # A credential-bearing target must trip BLOCKED even with a calm wording
        # and even if the person types yes.
        calls = []
        orig = actor._perform
        actor._perform = lambda a: calls.append(a)
        try:
            out = actor.gated_execute(
                Action(
                    ActionKind.CLICK_ELEMENT,
                    "open the next screen for you",
                    "Enter your admin password",
                ),
                read_input=lambda _p: "yes",
                write_output=lambda _m: None,
            )
        finally:
            actor._perform = orig
        self.assertFalse(out.performed)
        self.assertEqual(out.decision.risk, safety.Risk.BLOCKED)
        self.assertEqual(calls, [])

    def test_happy_path_targets_perform_without_prompting(self):
        # The text-size happy path: each routine target must execute with no
        # confirmation prompt (read_input must never be consulted).
        for target in ("Accessibility", "Display", "Text size", "Larger Text"):
            calls = []
            asked = []
            orig = actor._perform
            actor._perform = lambda a: calls.append(a.target)
            try:
                out = actor.gated_execute(
                    Action(
                        ActionKind.CLICK_ELEMENT,
                        "open the screen where text size lives",
                        target,
                    ),
                    read_input=lambda _p: asked.append(_p) or "",
                    write_output=lambda _m: None,
                )
            finally:
                actor._perform = orig
            self.assertTrue(out.performed, target)
            self.assertEqual(out.decision.risk, safety.Risk.ROUTINE, target)
            self.assertEqual(calls, [target])
            self.assertEqual(asked, [], f"{target} should not prompt")


# --- OPEN_APP allow-list (Fix 2) -------------------------------------------

class OpenAppAllowList(unittest.TestCase):
    """Only allow-listed apps may be activated, independent of the planner."""

    def test_open_app_outside_allow_list_does_not_perform(self):
        calls = []
        orig = actor._perform
        actor._perform = lambda a: calls.append(a)
        try:
            out = actor.gated_execute(
                # Benign-sounding description, off-list (and dangerous) target.
                Action(ActionKind.OPEN_APP, "open the settings app", "Terminal"),
                read_input=lambda _p: "yes",  # even a yes must not help.
                write_output=lambda _m: None,
            )
        finally:
            actor._perform = orig
        self.assertFalse(out.performed)
        self.assertFalse(out.allowed)
        self.assertEqual(calls, [])

    def test_open_app_system_settings_performs(self):
        calls = []
        asked = []
        orig = actor._perform
        actor._perform = lambda a: calls.append(a.target)
        try:
            out = actor.gated_execute(
                Action(ActionKind.OPEN_APP, "open System Settings", "System Settings"),
                read_input=lambda _p: asked.append(_p) or "",
                write_output=lambda _m: None,
            )
        finally:
            actor._perform = orig
        self.assertTrue(out.performed)
        self.assertEqual(out.decision.risk, safety.Risk.ROUTINE)
        self.assertEqual(calls, ["System Settings"])
        self.assertEqual(asked, [])  # routine: no prompt


# --- Scam shield fires -> hard stop before acting --------------------------

class ScamFireHardStops(unittest.TestCase):
    def test_scam_on_perceive_stops_before_any_action(self):
        acted = []

        def execute(a, **k):
            acted.append(a)
            return ActionOutcome(True, True,
                                 safety.ActionDecision(safety.Risk.ROUTINE))

        code, say = _run(
            describe=lambda _c, _i: (
                "Your computer is infected! Call this number now: 1-800-555-0199"
            ),
            propose=lambda _c, _d: _plan(),
            execute=execute,
        )
        self.assertEqual(code, 1)
        self.assertEqual(acted, [])  # never acted
        self.assertIn("scam", say.text)
        self.assertIn("family member", say.text)


# --- Bounds: step budget and time cap --------------------------------------

class Bounds(unittest.TestCase):
    def test_step_budget_safe_stops(self):
        # Planner always proposes a real action; screen always "changes" so no
        # retry path interferes. Budget must cap the run.
        seq = iter(range(1000))

        code, say = _run(
            config=loop.LoopConfig(step_budget=3, time_cap_seconds=999,
                                   pace_seconds=0),
            describe=lambda _c, _i: f"screen {next(seq)}",
            propose=lambda _c, _d: _plan(),
        )
        self.assertEqual(code, 1)
        self.assertIn("stopping here to be safe", say.text)

    def test_time_cap_safe_stops(self):
        clock = {"t": 0.0}
        loop_now = loop._now
        loop._now = lambda: clock["t"]
        try:
            def describe(_c, _i):
                clock["t"] += 100  # each perceive burns time
                return f"screen {clock['t']}"

            code, say = _run(
                config=loop.LoopConfig(step_budget=99, time_cap_seconds=50,
                                       pace_seconds=0),
                describe=describe,
                propose=lambda _c, _d: _plan(),
            )
        finally:
            loop._now = loop_now
        self.assertEqual(code, 1)
        self.assertIn("taking longer", say.text)


# --- Refused action (RISKY without yes) -> safe stop -----------------------

class RefusedActionSafeStops(unittest.TestCase):
    def test_gate_refusal_stops_loop(self):
        code, say = _run(
            propose=lambda _c, _d: _plan(desc="Open Privacy & Security",
                                         target="Privacy & Security"),
            execute=lambda a, **k: ActionOutcome(
                performed=False, allowed=False,
                decision=safety.ActionDecision(safety.Risk.RISKY, "private stuff"),
            ),
        )
        self.assertEqual(code, 1)
        self.assertIn("on my own", say.text)


# --- Low confidence -> safe stop, no acting --------------------------------

class LowConfidenceSafeStops(unittest.TestCase):
    def test_unsure_planner_stops(self):
        acted = []
        code, say = _run(
            propose=lambda _c, _d: _plan(
                confident=False, reason="I'm not sure what this screen is."),
            execute=lambda a, **k: (acted.append(a) or ActionOutcome(
                True, True, safety.ActionDecision(safety.Risk.ROUTINE))),
        )
        self.assertEqual(code, 1)
        self.assertEqual(acted, [])
        self.assertIn("not sure", say.text)


# --- Hard stop -> ends before next action ----------------------------------

class HardStop(unittest.TestCase):
    def test_stop_flag_ends_run_before_acting(self):
        acted = []
        code, say = _run(
            should_stop=lambda: True,  # set from the very start
            propose=lambda _c, _d: _plan(),
            execute=lambda a, **k: (acted.append(a) or ActionOutcome(
                True, True, safety.ActionDecision(safety.Risk.ROUTINE))),
        )
        self.assertEqual(code, 1)
        self.assertEqual(acted, [])
        self.assertIn("stop", say.text)


# --- Repeated failure: one gentle retry, then safe stop --------------------

class RepeatedFailure(unittest.TestCase):
    def test_unchanged_screen_retries_once_then_stops(self):
        # describe() always returns the same text -> screen never moves.
        attempts = []

        def execute(a, **k):
            attempts.append(a)
            return ActionOutcome(True, True,
                                 safety.ActionDecision(safety.Risk.ROUTINE))

        code, say = _run(
            describe=lambda _c, _i: "the very same screen, unchanged",
            propose=lambda _c, _d: _plan(),
            execute=execute,
        )
        self.assertEqual(code, 1)
        # One gentle re-attempt = it acted twice, then gave up (not a storm).
        self.assertEqual(len(attempts), 2)
        self.assertIn("once more", say.text)


# --- Done -> clean success -------------------------------------------------

class Done(unittest.TestCase):
    def test_done_plan_succeeds(self):
        code, say = _run(propose=lambda _c, _d: _done_plan())
        self.assertEqual(code, 0)
        self.assertIn("bigger", say.text)


# --- Errors become calm safe-stops, never crashes --------------------------

class ErrorsAreCalm(unittest.TestCase):
    def test_capture_error_is_calm(self):
        from grandson.screen import ScreenCaptureError

        def boom():
            raise ScreenCaptureError("I couldn't see the screen (plain message).")

        code, say = _run(capture=boom)
        self.assertEqual(code, 1)
        self.assertIn("couldn't see the screen", say.text)

    def test_action_error_is_calm(self):
        from grandson.actor import ActionError

        def execute(a, **k):
            raise ActionError("I'm not allowed to move the mouse yet.")

        code, say = _run(
            propose=lambda _c, _d: _plan(),
            execute=execute,
        )
        self.assertEqual(code, 1)
        self.assertIn("not allowed to move the mouse", say.text)


if __name__ == "__main__":
    unittest.main()
