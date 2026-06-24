"""M2 safety tests: the risky-action gate boundary + informed confirmation.

Run with the stdlib (no extra deps):

    PYTHONPATH=src python -m unittest tests.test_safety_m2 -v

These prove three things for the M2 task "make the on-screen text bigger":
  1. The happy path stays ROUTINE (no confirmation spam).
  2. Drift toward danger (Privacy & Security, Apple Account/payment, Allow/
     permission prompts, security/privacy setting changes) is RISKY, and
     credentials / Touch ID / admin-password dialogs and scam-flagged actions
     are BLOCKED (terminal).
  3. The informed-confirmation contract: typed `yes` only, no default-yes,
     one-yes-per-action, BLOCKED can never be confirmed.
And a benign regression set so M1's scam shield isn't degraded and the happy
path isn't over-flagged.
"""

import unittest

from grandson import safety
from grandson.safety import Risk


def risk_of(desc: str) -> Risk:
    return safety.classify_action(desc).risk


class HappyPathRoutine(unittest.TestCase):
    """The one M2 task's steps must stay ROUTINE."""

    ROUTINE_STEPS = [
        "Open System Settings",
        "Open the System Settings app",
        "Click on Accessibility in the sidebar",
        "Click Display in the Accessibility list",
        "Click the Display row under Accessibility",
        "Drag the Text Size slider to make the text bigger",
        "Move the text size slider one notch larger",
        "Click the larger text size option",
        "Turn on Bold text",
        "Increase the pointer (cursor) size",
        "Scroll down to find the text size control",
        "Read what is on the screen",
        "Move the mouse to the Accessibility button",
    ]

    def test_happy_path_steps_are_routine(self):
        for step in self.ROUTINE_STEPS:
            with self.subTest(step=step):
                self.assertEqual(
                    risk_of(step), Risk.ROUTINE,
                    f"happy-path step should be ROUTINE: {step!r}",
                )


class DriftIsRisky(unittest.TestCase):
    """Near-miss drift around the task must trip the gate as RISKY."""

    RISKY_STEPS = [
        # Privacy & Security pane — the dangerous neighbour.
        "Click Privacy & Security in the sidebar",
        "Open Privacy and Security settings",
        "Open the Privacy & Security pane",
        # Apple Account / payment / Wallet panes.
        "Open the Apple Account pane",
        "Click on Apple ID at the top of System Settings",
        "Open Wallet & Apple Pay",
        "Open Payment & Shipping",
        "Open iCloud settings",
        "Open Family Sharing",
        "Open Users & Groups",
        # Permission / Allow prompts and security-setting changes.
        "Click Allow in the permission dialog",
        "Grant permission to control the computer",
        "Change a privacy setting",
        "Change the security setting for this app",
        "Turn off the firewall",
        # The other always-risky §1 categories still hold.
        "Pay the invoice with a credit card",
        "Delete the file permanently",
        "Send the email to grandson@example.com",
        "Install this new app",
        "Call the number shown on the screen",
    ]

    def test_drift_steps_are_risky(self):
        for step in self.RISKY_STEPS:
            with self.subTest(step=step):
                self.assertEqual(
                    risk_of(step), Risk.RISKY,
                    f"drift/§1 step should be RISKY: {step!r}",
                )

    def test_grant_access_phrasing_at_least_stops(self):
        # "grant access" also reads as a remote-access scam pattern, which the
        # scam shield (always wins) escalates to BLOCKED. Either way the gate
        # trips and the action never auto-runs — that's the requirement. We pin
        # that it is NEVER ROUTINE.
        for step in [
            "Click the Allow button to grant access",
            "Allow remote access to the computer",
        ]:
            with self.subTest(step=step):
                self.assertIn(
                    risk_of(step), (Risk.RISKY, Risk.BLOCKED),
                    f"grant/allow-access step must never be ROUTINE: {step!r}",
                )


class CredentialsAndScamsAreBlocked(unittest.TestCase):
    """Credentials, auth dialogs, and scam-flagged actions are BLOCKED (terminal)."""

    BLOCKED_STEPS = [
        "Type the login password into the box",
        "Enter your administrator password to apply changes",
        "Enter the admin password",
        "Confirm with Touch ID",
        "Use Face ID to unlock this setting",
        "Click the lock to make changes, then enter your password",
        "Type the verification code from your phone",
        "Enter your PIN",
        "Sign in to your Apple ID with your password",
    ]

    def test_credentials_and_auth_are_blocked(self):
        for step in self.BLOCKED_STEPS:
            with self.subTest(step=step):
                self.assertEqual(
                    risk_of(step), Risk.BLOCKED,
                    f"credential/auth step should be BLOCKED: {step!r}",
                )

    def test_scam_flagged_action_is_blocked(self):
        d = safety.classify_action(
            "Click the button that says your computer is infected, call this number"
        )
        self.assertEqual(d.risk, Risk.BLOCKED)
        self.assertIn("scam", d.reason.lower())

    def test_empty_description_is_risky_not_routine(self):
        self.assertEqual(risk_of(""), Risk.RISKY)
        self.assertEqual(risk_of("   "), Risk.RISKY)


class InformedAffirmative(unittest.TestCase):
    """is_affirmative: only the full word `yes` is acceptance."""

    def test_yes_variants_accept(self):
        for raw in ["yes", "YES", " Yes ", "yEs\n", "\tyes\t"]:
            with self.subTest(raw=raw):
                self.assertTrue(safety.is_affirmative(raw))

    def test_everything_else_rejects(self):
        for raw in ["", " ", "\n", "y", "Y", "ok", "okay", "sure",
                    "yes please", "yeah", "yep", "no", "yes no", "1", None]:
            with self.subTest(raw=raw):
                self.assertFalse(safety.is_affirmative(raw))


class ConfirmRiskyAction(unittest.TestCase):
    """The injectable confirmation flow."""

    def _decision(self, risk, reason="because reasons"):
        return safety.ActionDecision(risk=risk, reason=reason)

    def _capture(self, typed):
        """Return (read_input, write_output, outbox) where read_input yields `typed`."""
        outbox = []

        def write_output(msg):
            outbox.append(msg)

        def read_input(_prompt):
            return typed

        return read_input, write_output, outbox

    def test_typed_yes_approves_risky(self):
        ri, wo, out = self._capture("yes")
        res = safety.confirm_risky_action(
            self._decision(Risk.RISKY), "open Privacy & Security",
            read_input=ri, write_output=wo,
        )
        self.assertTrue(res.approved)
        # The plain-language reason was shown before asking (informed).
        shown = "\n".join(out)
        self.assertIn("because reasons", shown)
        self.assertIn("open Privacy & Security", shown)

    def test_bare_enter_does_not_approve(self):
        ri, wo, _ = self._capture("")
        res = safety.confirm_risky_action(
            self._decision(Risk.RISKY), "open Privacy & Security",
            read_input=ri, write_output=wo,
        )
        self.assertFalse(res.approved)

    def test_y_does_not_approve(self):
        ri, wo, _ = self._capture("y")
        res = safety.confirm_risky_action(
            self._decision(Risk.RISKY), "x", read_input=ri, write_output=wo,
        )
        self.assertFalse(res.approved)

    def test_blocked_is_never_confirmed_even_with_yes(self):
        ri, wo, out = self._capture("yes")
        res = safety.confirm_risky_action(
            self._decision(Risk.BLOCKED), "type the admin password",
            read_input=ri, write_output=wo,
        )
        self.assertFalse(res.approved)
        # It must NOT have asked for input at all; it should explain it can't.
        shown = "\n".join(out).lower()
        self.assertIn("can't do this", shown)

    def test_blocked_does_not_read_input(self):
        # If it tried to read input on BLOCKED, this would raise.
        def explode(_prompt):
            raise AssertionError("BLOCKED must never read input")

        res = safety.confirm_risky_action(
            self._decision(Risk.BLOCKED), "type the admin password",
            read_input=explode, write_output=lambda _m: None,
        )
        self.assertFalse(res.approved)

    def test_routine_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            safety.confirm_risky_action(
                self._decision(Risk.ROUTINE), "open System Settings",
                read_input=lambda _p: "yes", write_output=lambda _m: None,
            )

    def test_eof_is_treated_as_no(self):
        def eof(_prompt):
            raise EOFError

        res = safety.confirm_risky_action(
            self._decision(Risk.RISKY), "x",
            read_input=eof, write_output=lambda _m: None,
        )
        self.assertFalse(res.approved)


class GateAction(unittest.TestCase):
    """The single safe entry contract the builder wires control through."""

    def test_routine_allowed_without_prompting(self):
        def explode(_prompt):
            raise AssertionError("ROUTINE must not prompt")

        res = safety.gate_action(
            "Open System Settings", read_input=explode, write_output=lambda _m: None,
        )
        self.assertTrue(res.allowed)
        self.assertEqual(res.decision.risk, Risk.ROUTINE)

    def test_risky_allowed_only_with_typed_yes(self):
        yes = safety.gate_action(
            "Click Privacy & Security",
            read_input=lambda _p: "yes", write_output=lambda _m: None,
        )
        self.assertTrue(yes.allowed)
        self.assertEqual(yes.decision.risk, Risk.RISKY)

        no = safety.gate_action(
            "Click Privacy & Security",
            read_input=lambda _p: "", write_output=lambda _m: None,
        )
        self.assertFalse(no.allowed)

    def test_blocked_never_allowed(self):
        res = safety.gate_action(
            "Type the admin password",
            read_input=lambda _p: "yes", write_output=lambda _m: None,
        )
        self.assertFalse(res.allowed)
        self.assertEqual(res.decision.risk, Risk.BLOCKED)


class BenignRegression(unittest.TestCase):
    """Don't regress M1's scam shield and don't over-flag everyday narration."""

    def test_benign_screens_stay_clear(self):
        benign = [
            "You are looking at the System Settings window. On the left is a list "
            "of settings like Wi-Fi, Bluetooth, and Accessibility.",
            "This is the Accessibility screen. There is a Display option you can "
            "click to make text bigger.",
            "Your email inbox is open with three new messages from friends.",
            "A document is open in TextEdit with a grocery list.",
        ]
        for text in benign:
            with self.subTest(text=text[:40]):
                self.assertTrue(
                    safety.scan_for_scams(text).is_clear,
                    f"benign screen should be clear: {text[:40]!r}",
                )

    def test_known_scams_still_fire(self):
        scams = [
            "Your computer is infected! Call this number now: 1-800-555-0199",
            "We are from Microsoft support and need remote access via AnyDesk.",
            "Congratulations, you have won the lottery! Send a gift card to claim.",
        ]
        for text in scams:
            with self.subTest(text=text[:40]):
                self.assertFalse(
                    safety.scan_for_scams(text).is_clear,
                    f"known scam should fire: {text[:40]!r}",
                )

    def test_apple_support_url_not_overflagged(self):
        # A real apple.com host must not trip the look-alike check.
        self.assertTrue(
            safety.scan_for_scams("See https://support.apple.com/guide").is_clear
        )


if __name__ == "__main__":
    unittest.main()
