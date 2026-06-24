"""The safety seam.

The full safety policy lives in ``docs/SAFETY.md`` and OVERRIDES every other
goal. This module is the single, well-named place where that policy gets
enforced in code.

In M1 ("See & Explain") there is no screen control, so there is nothing risky to
gate yet. These functions are deliberate *stubs* — they define the shape of the
contract so the rest of the app already calls through the safety layer. The
``safety-security`` agent fills in the real logic in M2 (the risky-action gate)
and M3 (the always-on scam shield).

Do not delete or bypass these seams to "just make it work." The whole product
is built on the promise that nothing risky happens without passing through here.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum


class Risk(Enum):
    """How an action is treated by the safety gate (see SAFETY.md §1)."""

    ROUTINE = "routine"  # proceed, with narration
    RISKY = "risky"      # STOP, explain in plain language, require an explicit yes
    BLOCKED = "blocked"  # do not do this at all (e.g. a flagged scam)


@dataclass
class ActionDecision:
    """The verdict on a proposed action."""

    risk: Risk
    # A plain-language reason the person can understand (SAFETY.md §4).
    reason: str = ""


@dataclass
class ScamFinding:
    """One thing on screen that looks like a scam (see SAFETY.md §2)."""

    label: str          # short name, e.g. "fake virus warning"
    explanation: str    # plain-language why it's dangerous and what to do


@dataclass
class ScamScanResult:
    """The result of scanning what's on screen for scams."""

    findings: list[ScamFinding] = field(default_factory=list)

    @property
    def is_clear(self) -> bool:
        return not self.findings


# One short, plain-language line we attach to every scam finding (SAFETY.md §2 +
# §4): stop, don't proceed, and offer to bring in a trusted family member. Kept
# as a constant so the wording is consistent everywhere the shield speaks.
FAMILY_CONTACT_ADVICE = (
    "Please don't do what it asks, and don't call any number or click anything "
    "on it. This is exactly the kind of thing that tricks people. If you'd like, "
    "I can help you reach a family member you trust so you can check together."
)


def _advise(message: str) -> str:
    """Plain-language danger note + the standard family-contact offer."""
    return f"{message} {FAMILY_CONTACT_ADVICE}"


# ---------------------------------------------------------------------------
# Scam shield (SAFETY.md §2) — deterministic keyword/pattern rules.
#
# Each rule is (label, plain-language danger note, list of trigger patterns).
# A rule fires if ANY of its patterns appears in the (lower-cased) text. We
# favor recall on purpose: a false alarm just asks the person to double-check,
# while a missed scam can cost them everything (task brief + SAFETY.md §2).
#
# Patterns are matched case-insensitively as substrings unless they look like a
# regex (we compile them all as regex; plain words are valid regex too). Word
# boundaries are used where a short token could otherwise match inside an
# unrelated word.
# ---------------------------------------------------------------------------

_SCAM_RULES: list[tuple[str, str, list[str]]] = [
    (
        "fake virus warning",
        "This looks like a fake warning trying to scare you. Real virus alerts "
        "never take over your screen and tell you to call a phone number.",
        [
            r"your (computer|pc|mac|device|system) (is|has been|may be) "
            r"(infected|hacked|compromised|locked|at risk)",
            r"\bvirus(es)? (detected|found)\b",
            r"\bmalware (detected|found)\b",
            r"\bthreats? (detected|found)\b",
            r"\btrojan\b",
            r"\bspyware\b",
            r"\byour (computer|pc|mac) (is|has been) blocked\b",
            r"\bsecurity (alert|warning)\b",
            r"\bcritical (alert|warning|error)\b",
            r"\bsystem (warning|alert) ?!",
            r"\bdo not (turn off|restart|shut down) your (computer|pc|mac)\b",
        ],
    ),
    (
        "fake support phone number",
        "It is pushing you to phone a number that popped up on the screen. "
        "That number reaches the scammers, not a real company.",
        [
            r"call (us |now |immediately |this number |our )?(toll[- ]?free )?"
            r"(at |on )?\+?[\d][\d\-\s().]{6,}",
            r"call (microsoft|apple|amazon|windows|google) (support|security|help)",
            r"call (the )?(support|help ?line|technician|number) (now|immediately)",
            r"dial \+?[\d][\d\-\s().]{6,}",
            r"\bphone\s+\+?[\d][\d\-\s().]{6,}",
            r"\+?[\d][\d\-\s().]{6,}\bto (secure|verify|unlock|reactivate|"
            r"restore|protect|confirm) your (account|id|identity)\b",
            r"contact (microsoft|apple|amazon) support (immediately|now)",
            r"phone (number )?(below|above|shown|displayed)",
        ],
    ),
    (
        "tech-support impersonation",
        "Someone is pretending to be from a big company like Microsoft, Apple, "
        "or Amazon. Those companies do not contact you this way or watch your "
        "screen.",
        [
            r"(microsoft|apple|amazon|windows|google|norton|mcafee|geek squad)"
            r".{0,30}(support|security|technician|help ?desk|service team)",
            r"(support|security|technician).{0,30}"
            r"(microsoft|apple|amazon|windows|norton|mcafee)",
            r"\bwindows defender\b",
            r"\bfrom (the )?(microsoft|apple|amazon) (team|security|support)\b",
            r"your (microsoft|apple|amazon|icloud) (id |account )?(has been|is|was) "
            r"(suspended|locked|compromised|disabled|restricted)",
            r"\bapple id\b.{0,40}\b(locked|suspended|disabled|compromised|"
            r"restricted|verify|confirm)\b",
            r"\bverify your (account|identity) (immediately|now|to avoid)\b",
        ],
    ),
    (
        "remote-access request",
        "It wants you to install a program that lets a stranger control your "
        "computer from far away. If you do that, they can see and take "
        "everything.",
        [
            r"\banydesk\b",
            r"\bteamviewer\b",
            r"\bteam viewer\b",
            r"\blogmein\b",
            r"\bultraviewer\b",
            r"\bquick ?assist\b",
            r"\bremote (access|desktop|connection|support|control)\b",
            r"\b(let|allow|give) (us|me|them) (access to|control of|remote)\b",
            r"\bgrant (remote )?access\b",
            r"\bso (i|we) can (access|connect to|control) your (computer|screen)\b",
            r"\b(log|sign) ?in(to)?\b.{0,30}\byour (computer|machine|pc|mac|"
            r"laptop|desktop|device)\b",
            r"\b(access|connect to|control|get into|get on)\b.{0,20}"
            r"\byour (machine|pc|laptop|desktop)\b",
            r"\b(remote|remotely)\b.{0,30}\byour (machine|computer|pc|laptop|"
            r"desktop|device)\b",
        ],
    ),
    (
        "urgency and secrecy pressure",
        "It is rushing you and telling you to keep it secret. Real, honest help "
        "never works that way. Pressure and secrecy are how scams trap people.",
        [
            r"\bact (now|fast|immediately|within)\b",
            r"\b(in|within|you have) \d+ (minutes?|hours?|seconds?)\b",
            r"\bdo not (tell|talk to|inform|call) (anyone|your family|the bank|"
            r"anybody)\b",
            r"\bdon'?t tell (anyone|your family|anybody|the bank)\b",
            r"\bkeep this (a )?(secret|confidential|between us|private)\b",
            r"\b(this is )?(your )?(final|last) (warning|notice|chance)\b",
            r"\b(account|offer|access) (will be|is about to be) "
            r"(suspended|closed|locked|deleted|terminated)\b",
            r"\bimmediate action (is )?required\b",
            r"\bexpires? (in|within|today|soon)\b",
        ],
    ),
    (
        "gift-card or unusual-payment demand",
        "It is asking to be paid with gift cards, wire transfers, or "
        "cryptocurrency. No real company or government office is ever paid that "
        "way. This is a sure sign of a scam.",
        [
            r"\bgift ?cards?\b",
            r"\b(itunes|google play|amazon|steam|ebay) (gift )?cards?\b",
            r"\bwire (transfer|the money|funds)\b",
            r"\b(bitcoin|btc|crypto(currency)?|ethereum|usdt)\b",
            r"\bmoney ?gram\b",
            r"\bwestern union\b",
            r"\bbuy .{0,20}(gift )?cards?\b",
            r"\bsend (the )?(money|payment|funds) (now|immediately|to)\b",
            r"\bpay (a )?(fee|fine|tax) (to release|to unlock|now)\b",
        ],
    ),
    (
        "prize, lottery, or inheritance scam",
        "It claims you won money or were left an inheritance you never expected. "
        "These are made up to get your details or a 'fee' out of you.",
        [
            r"\byou'?ve? (just )?won\b",
            r"\b(congratulations|congrats).{0,40}(won|winner|selected|prize)\b",
            r"\b(lottery|sweepstakes|jackpot|prize|grand prize)\b",
            r"\b(claim|collect) your (prize|reward|winnings|inheritance)\b",
            r"\binheritance\b",
            r"\bunclaimed (funds|money|inheritance)\b",
            r"\bbeneficiary of (a |an )?(fund|estate|sum)\b",
            r"\bmillion (dollars|usd|pounds|euros)\b",
            r"\byou (have been|were) (selected|chosen) (as|to)\b",
        ],
    ),
    (
        "refund or overpayment scam",
        "It says you are owed a refund or that you were overpaid. This trick "
        "gets people to share bank details or 'send back' money that was never "
        "really there.",
        [
            r"\b(you are |you're |we owe you )?(due|owed|entitled to) a refund\b",
            r"\brefund (of )?\$?[\d,]+",
            r"\bover ?(paid|payment|charged)\b",
            r"\b(send|pay|return) (back |us )?the (difference|extra|overpayment)\b",
            r"\byour (subscription|renewal|order) (has been|will be) "
            r"(charged|renewed|billed)\b.{0,60}(refund|cancel|call)",
            r"\b(geek squad|norton|mcafee|paypal) .{0,30}(renewal|invoice|charge)\b",
            r"\bto (cancel|dispute) (this )?(charge|order|renewal),? (call|contact)\b",
        ],
    ),
    (
        "romance scam",
        "Someone you met online is asking for money or gift cards, often after "
        "moving fast and avoiding meeting in person. This is a common heartbreak "
        "scam.",
        [
            r"\b(my (love|dear|darling|honey))\b.{0,60}(money|help|funds|stuck)",
            r"\b(stuck|stranded) (abroad|overseas|in another country)\b",
            r"\b(send|need|wire) (me )?(some )?money\b.{0,40}(love|dear|darling|"
            r"emergency|flight|ticket)",
            r"\bi (love|need) you\b.{0,40}(money|gift card|western union|bitcoin)",
        ],
    ),
]


# A separate, gentler check for links/URLs (SAFETY.md §2: show the real URL,
# never just the text). We surface the actual destination so the person can see
# where a link really goes. This is informational unless the URL also looks
# deceptive (an IP address, an unexpected look-alike, etc.).
_URL_RE = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)
_IP_URL_RE = re.compile(r"https?://\d{1,3}(\.\d{1,3}){3}", re.IGNORECASE)

# Brand names that scammers love to imitate inside a misleading domain.
_LOOKALIKE_BRANDS = (
    "apple", "icloud", "microsoft", "windows", "amazon", "paypal", "google",
    "netflix", "bank", "wellsfargo", "chase", "norton", "mcafee", "usps",
    "fedex", "irs",
)


def _scan_links(text: str) -> list[ScamFinding]:
    """Surface real URLs and flag the ones that look deceptive (SAFETY.md §2)."""
    findings: list[ScamFinding] = []
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(".,);")
        host = _host_of(url)
        if not host:
            continue

        if _IP_URL_RE.match(url):
            findings.append(
                ScamFinding(
                    label="suspicious link",
                    explanation=_advise(
                        f"There is a link that points to {url} . A real company's "
                        "link looks like a normal website name, not a string of "
                        "numbers like this. This is a warning sign."
                    ),
                )
            )
            continue

        impersonated = _impersonated_brand(host)
        if impersonated:
            findings.append(
                ScamFinding(
                    label="misleading link",
                    explanation=_advise(
                        f"There is a link that uses the name '{impersonated}' but "
                        f"actually goes to '{host}', which is not the real "
                        f"{impersonated} website. Scammers do this to look real."
                    ),
                )
            )
    return findings


def _host_of(url: str) -> str:
    """Pull the host out of a URL without importing urllib for one job."""
    rest = url.split("://", 1)[-1]
    host = rest.split("/", 1)[0].split("?", 1)[0]
    host = host.split("@")[-1]  # strip any user:pass@ trick
    host = host.split(":", 1)[0]  # strip port
    return host.lower()


# Second-level labels that are really part of a public suffix (so the brand sits
# one label further left). Small, common-for-our-users list; recall-first.
_CCSLD_LABELS = {"co", "com", "org", "net", "gov", "edu", "ac"}


# Map a digit/symbol to the letter scammers swap it in for, so we can spot
# typo-squat look-alikes like "amaz0n" (0->o), "g00gle", "paypa1" (1->l).
_LEET_MAP = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t"})


def _impersonated_brand(host: str) -> str:
    """Return a brand name if the host looks like it's imitating a real brand.

    Conservative and recall-first. We flag a host as a look-alike when:

    1. A brand word appears somewhere in the host but the *registrable* domain
       isn't that brand, e.g. ``apple.security-check.com`` -> "apple".
    2. The registrable label contains the brand as a hyphen-joined token but is
       not exactly the brand, e.g. ``usps-redelivery`` -> "usps".
    3. The registrable label is a typo-squat of a brand after undoing common
       character swaps (0->o, 1->l, etc.), e.g. ``amaz0n`` -> "amazon".

    We never flag a label that *is* exactly the brand (e.g. ``apple.com``,
    ``apple.co.uk``), so legitimate brand domains stay clear.
    """
    labels = host.split(".")
    if len(labels) < 2:
        return ""
    # The registrable name is the label just left of the public suffix. For most
    # hosts that's the second-to-last label ("example" in "example.com"), but for
    # multi-part country suffixes ("amazon.co.uk", "bank.com.au") it's one
    # further left, so we skip a known two-part suffix.
    suffix_len = 2 if len(labels) >= 3 and labels[-2] in _CCSLD_LABELS else 1
    registrable = labels[-1 - suffix_len]
    registrable_tokens = set(re.split(r"[-_]", registrable))
    deleeted = registrable.translate(_LEET_MAP)

    for brand in _LOOKALIKE_BRANDS:
        # The real thing: brand is exactly the registrable label -> legitimate.
        if registrable == brand:
            return ""
    for brand in _LOOKALIKE_BRANDS:
        # 1. Brand appears in host but not in the registrable label at all.
        if brand in host and brand not in registrable:
            return brand
        # 2. Brand is a hyphen/underscore-joined token of the registrable label.
        if brand in registrable_tokens:
            return brand
        # 3. Typo-squat: registrable label decodes to the brand (or brand-in-token)
        #    only after undoing character swaps (so a digit was involved).
        if deleeted != registrable:
            if deleeted == brand or brand in set(re.split(r"[-_]", deleeted)):
                return brand
    return ""


def scan_for_scams(screen_text_or_description: str) -> ScamScanResult:
    """Look at what's on screen for scam patterns (SAFETY.md §2).

    The always-on scam shield. Runs deterministic keyword/pattern rules over the
    narration text (or any screen text) and returns plain-language findings for
    anything that looks like one of the §2 scam patterns: fake virus popups,
    tech-support impersonation, urgency + secrecy, gift-card/unusual-payment
    demands, remote-access lures, prize/lottery/inheritance and
    refund/overpayment cons, romance scams, and misleading links.

    Design choices (per task brief and SAFETY.md):
    - **Recall first.** A false alarm just asks the person to double-check; a
      missed scam can cost them everything. When in doubt, we flag.
    - **Plain language (§4).** Every finding explains the danger in short, simple
      sentences with no jargon, and offers to loop in a trusted family member.
    - **Deterministic and auditable.** No extra model call — the rules above are
      readable and reviewable. (See module-level note for the M2/M3 idea of also
      scanning raw OCR text, not just the narration.)

    Returns an empty result ("all clear") when nothing matches.
    """
    if not screen_text_or_description:
        return ScamScanResult(findings=[])

    # Run the prose keyword rules against text with URLs blanked out: a hostname
    # like "support.apple.com" must NOT trip the "apple ... support" prose rule.
    # Links get their own dedicated, host-aware check below (_scan_links).
    text = _URL_RE.sub(" ", screen_text_or_description.lower())
    findings: list[ScamFinding] = []
    seen_labels: set[str] = set()

    for label, danger_note, patterns in _SCAM_RULES:
        if label in seen_labels:
            continue
        for pattern in patterns:
            if re.search(pattern, text):
                findings.append(
                    ScamFinding(label=label, explanation=_advise(danger_note))
                )
                seen_labels.add(label)
                break

    # Links are scanned against the original text to preserve the real URLs.
    findings.extend(_scan_links(screen_text_or_description))

    return ScamScanResult(findings=findings)


# ---------------------------------------------------------------------------
# Risky-action gate (SAFETY.md §1).
#
# Classify a proposed action as ROUTINE, RISKY, or BLOCKED.
#
# BLOCKED  — must NEVER auto-run and can NEVER be confirmed/unblocked (M2-PLAN
#            §"How a 'yes' is captured": BLOCKED is terminal). We reserve this
#            for the things Grandson must never do on someone's behalf even with
#            a yes: typing a credential (password/PIN/2FA/SSN) or going through
#            a Touch ID / admin-password authentication dialog (M2-PLAN non-goal
#            #2 — "it never types a credential"; it hands the keyboard back),
#            and anything the scam shield flagged (M2-PLAN §4 — scam fires →
#            hard stop, no proceeding).
# RISKY    — STOP, explain in plain language, require an informed typed `yes`
#            (everything else on SAFETY.md §1's "always risky" list, plus the
#            System-Settings drift cases for this M2 task: Privacy & Security,
#            Apple-Account/payment panes, Allow/permission prompts, and any
#            security-or-privacy setting change).
# ROUTINE  — proceed with narration (this task's happy path: open System
#            Settings, navigate to Accessibility → Display, drag/click the
#            text-size control, Bold text, cursor size).
#
# Each rule is (matcher patterns, plain-language reason). The reason is written
# to be read aloud to someone who has never used a computer confidently (§4),
# and is reused verbatim as the body of the informed-confirmation prompt (§5),
# so the "yes" is genuinely informed.
#
# ORDER MATTERS: BLOCKED rules are checked before RISKY rules, and the scam
# shield is checked before both, so the strongest verdict always wins.
# ---------------------------------------------------------------------------

# BLOCKED: never auto-run, never confirmable. Typing a credential or going
# through an authentication dialog. Grandson hands the keyboard to the person
# instead — it does not type these even with a yes (M2-PLAN non-goal #2).
_BLOCKED_ACTION_RULES: list[tuple[list[str], str]] = [
    (
        [
            r"\bpassword\b", r"\bpasscode\b", r"\bpassphrase\b", r"\bpin\b",
            r"\b2fa\b", r"\btwo[- ]factor\b", r"\bone[- ]time (code|password)\b",
            r"\botp\b", r"\bverification code\b", r"\bsecurity code\b",
            r"\bssn\b", r"\bsocial security (number)?\b",
            r"\btouch ?id\b", r"\bface ?id\b", r"\bfingerprint\b",
            r"\b(admin|administrator)('s)? (password|credential)\b",
            r"\bauthenticat(e|ion)\b", r"\bunlock (this|the|your) (setting|pane|"
            r"lock|preferences?)\b", r"\bclick the lock\b",
            r"\benter (your |the )?(login|account|user|admin) (password|details|"
            r"credentials)\b",
            r"\bsign ?in (to|with) your (apple|icloud) (id|account)\b",
        ],
        "This is asking for something private and powerful — like your password, "
        "PIN, security code, or fingerprint. I will never type these for you, "
        "even if you ask me to. If a box like this appears, I will stop and let "
        "you type it yourself with your own hands, so it stays yours alone.",
    ),
]

_RISKY_ACTION_RULES: list[tuple[list[str], str]] = [
    (
        # System Settings DRIFT (M2 task boundary): the dangerous panes that sit
        # right next to Accessibility. Navigating into or touching any of these
        # is never part of "make the text bigger" — if it's proposed, stop.
        [
            r"\bprivacy (and|&|and/or) security\b", r"\bprivacy & security\b",
            r"\bprivacy and security\b",
            r"\b(apple|app[- ]?store) (id|account)\b",
            r"\bapple account\b", r"\bicloud (settings|account)\b",
            r"\bfamily sharing\b", r"\bpayment (and|&) shipping\b",
            r"\bwallet (and|&) apple pay\b", r"\bapple pay\b",
            r"\bgame center\b.{0,20}\b(account|sign)\b",
            r"\busers? (and|&) groups\b",
            r"\bnetwork\b.{0,20}\b(firewall|vpn|proxy)\b",
            r"\b(general)\b.{0,20}\b(profiles?|device management|sharing)\b",
        ],
        "This would move into a part of System Settings that controls your "
        "private information, your Apple Account, or your money — not the simple "
        "text-size screen we came for. We do not need to touch this to make the "
        "text bigger, so I will stop here and check with you first.",
    ),
    (
        [
            r"\b(pay|paying|payment)\b", r"\b(buy|buying|purchase|order)\b",
            r"\b(transfer|transferring|send) (money|funds|cash|\$)\b",
            r"\bwire\b", r"\bcheckout\b", r"\bcredit card\b", r"\bdebit card\b",
            r"\bcard number\b", r"\bbank (account|details)\b",
            r"\brouting number\b", r"\$\s?\d", r"\bvenmo\b", r"\bpaypal\b",
            r"\bzelle\b", r"\bsubscrib(e|ing)\b", r"\bdonat(e|ion)\b",
        ],
        "This involves money — paying, buying, or sending funds, or entering "
        "your card or bank details. Money can't always be gotten back once it's "
        "sent, so I'll stop and let you decide.",
    ),
    (
        [
            r"\bdelet(e|ing)\b", r"\b(erase|erasing)\b", r"\bremov(e|ing)\b",
            r"\bformat(ting)?\b", r"\bwip(e|ing)\b", r"\b(trash|empty trash)\b",
            r"\buninstall(ing)?\b", r"\bpermanently\b",
        ],
        "This would delete or permanently remove something. Once it's gone it "
        "may be impossible to get back, so I'll check with you first.",
    ),
    (
        [
            r"\bsend(ing)?\b", r"\b(reply|replying)\b", r"\bforward(ing)?\b",
            r"\bpost(ing)?\b", r"\bpublish(ing)?\b", r"\bsubmit(ting)?\b",
            r"\b(email|message|text|comment) (to|out)\b", r"\bshare\b",
        ],
        "This would send something out — like an email, a message, or a post — "
        "that other people will see. I'll show you the full thing first so you "
        "can read it before it goes.",
    ),
    (
        [
            r"\binstall(ing)?\b", r"\bdownload(ing)?\b", r"\bset ?up\b",
            r"\b(app|software|program|extension|plug ?in|update)\b.{0,20}"
            r"\b(install|download|add|get)\b",
            r"\b(get|add)\b.{0,20}\b(app|software|program|extension|plug ?in)\b",
            r"\bapp store\b", r"\bplay store\b",
            r"\bopen (the )?(downloaded|attached) (file|app)\b",
        ],
        "This would add new software to your computer. Bad software is one of the "
        "main ways people get tricked, so I'll always ask before installing "
        "anything.",
    ),
    (
        [
            r"\bgrant(ing)? (permission|access)\b", r"\ballow access\b",
            r"\b(click|tap|press|choose|select|hit)\s+(the\s+)?[\"']?allow[\"']?\b",
            r"\b(permission|privacy) settings?\b", r"\bsecurity settings?\b",
            r"\benable\b.{0,20}\b(access|permission|microphone|camera|location)\b",
            r"\b(turn off|disable)\b.{0,20}\b(firewall|protection|security|"
            r"antivirus|gatekeeper)\b",
            r"\bsystem (settings|preferences)\b.{0,30}\b(privacy|security)\b",
            r"\bchange (the )?(security|privacy) (setting|option)\b",
        ],
        "This would change a safety setting on your computer or give a program "
        "permission to do more. Getting this wrong can leave you exposed, so I'll "
        "stop and explain before anything changes.",
    ),
    (
        [
            r"\bcall\b.{0,30}\b(number|phone)\b",
            r"\bcall (this|that|the) number\b",
            r"\bdial\b", r"\bphone (this|that|the) number\b",
            r"\bcall (microsoft|apple|amazon|support)\b",
        ],
        "This would call a phone number shown on the screen. Numbers in popups "
        "and warnings often reach scammers, not real companies. I won't dial it "
        "on my own.",
    ),
]


def classify_action(description: str) -> ActionDecision:
    """Decide whether a proposed action is routine, risky, or blocked (SAFETY.md §1).

    Returns an ``ActionDecision`` whose ``reason`` is plain-language (§4) and
    reusable verbatim as the body of the informed-confirmation prompt (§5).

    ``Risk.ROUTINE`` — reading, scrolling, opening a normal app, moving the
    mouse, and this M2 task's happy path: opening System Settings, navigating
    to Accessibility → Display, and dragging/clicking the text-size control
    (Bold text, cursor size). These proceed with narration.

    ``Risk.BLOCKED`` — must NEVER auto-run and can NEVER be confirmed/unblocked
    (terminal):
      - typing/revealing a credential (password, PIN, 2FA/OTP code, SSN), or
        going through a Touch ID / Face ID / admin-password authentication
        dialog — Grandson hands the keyboard to the person instead (M2-PLAN
        non-goal #2)
      - anything the scam shield flagged in the same text (M2-PLAN §4: a scam
        finding hard-stops the task)

    ``Risk.RISKY`` — STOP, explain in plain language, require an informed typed
    `yes` (§5). Everything else on §1's "always risky" list plus this task's
    drift cases:
      - navigating into / touching Privacy & Security
      - the Apple-Account / payment / Wallet panes
      - any money action; deleting/removing; sending; installing/downloading
      - granting permission / an "Allow" prompt / changing a security or
        privacy setting
      - calling a phone number from the screen

    "When in doubt, treat it as risky" (§1): an empty/unclear description is
    treated as risky rather than waved through.

    Order of checks (strongest verdict wins): scam shield → BLOCKED rules →
    RISKY rules → ROUTINE.

    No control code calls this in M1; M2 routes every proposed action through it.
    """
    if not description or not description.strip():
        return ActionDecision(
            risk=Risk.RISKY,
            reason=(
                "I'm not sure what this action would do, so to be safe I'll stop "
                "and ask you before doing anything."
            ),
        )

    text = description.lower()

    # 1. Scam shield first. If the action's text trips the always-on shield, the
    # action touches a flagged screen. §1 calls that risky; M2-PLAN §4 goes
    # further and hard-stops the task — so this is BLOCKED (terminal), never a
    # "confirm and proceed."
    scan = scan_for_scams(description)
    if not scan.is_clear:
        labels = ", ".join(sorted({f.label for f in scan.findings}))
        return ActionDecision(
            risk=Risk.BLOCKED,
            reason=(
                "This is tied to something that looks like a scam "
                f"({labels}), so I will not do it at all. "
                + FAMILY_CONTACT_ADVICE
            ),
        )

    # 2. BLOCKED rules: credentials and authentication dialogs. Never auto-run,
    # never confirmable — Grandson does not type these even with a yes.
    for patterns, reason in _BLOCKED_ACTION_RULES:
        for pattern in patterns:
            if re.search(pattern, text):
                return ActionDecision(risk=Risk.BLOCKED, reason=reason)

    # 3. RISKY rules: stop and require an informed typed yes.
    for patterns, reason in _RISKY_ACTION_RULES:
        for pattern in patterns:
            if re.search(pattern, text):
                return ActionDecision(risk=Risk.RISKY, reason=reason)

    return ActionDecision(
        risk=Risk.ROUTINE,
        reason="This is an everyday step with nothing risky, so I can go ahead.",
    )


# ---------------------------------------------------------------------------
# Informed-confirmation contract (SAFETY.md §5; M2-PLAN §"How a 'yes' is
# captured as informed").
#
# A "yes" only counts if the person was shown, in plain language, exactly what
# will happen, AND they typed the full word `yes`. This is the ONE place that
# decides what counts as a yes. The builder MUST call `confirm_risky_action`
# rather than rolling their own prompt, so the confirmation semantics can never
# be gotten wrong (no default-yes, one-yes-per-action, BLOCKED is terminal).
# ---------------------------------------------------------------------------

# The only string that counts as acceptance, after trimming and lower-casing.
# A bare Enter, "y", "ok", "yes please", "", or anything else is treated as NO.
_AFFIRMATIVE = "yes"


def is_affirmative(raw_input: str) -> bool:
    """Return True only if ``raw_input`` is an informed, explicit yes.

    The rule (SAFETY.md §5; M2-PLAN): acceptance requires the person to type the
    full word ``yes`` (case-insensitive, surrounding whitespace ignored).
    Everything else — empty string, a bare Enter, ``"y"``, ``"ok"``,
    ``"yes please"``, ``"sure"``, or anything else — is **not** a yes.

    Kept as a tiny pure function so the accept/reject rule is unit-testable on
    its own and reused by ``confirm_risky_action``.
    """
    if raw_input is None:
        return False
    return raw_input.strip().lower() == _AFFIRMATIVE


def build_confirmation_prompt(decision: ActionDecision, human_description: str) -> str:
    """Build the plain-language text shown before asking for a typed yes (§5).

    Reuses ``decision.reason`` (already written in plain language by the gate)
    plus the specific ``human_description`` of the one action, so the person is
    shown *exactly* what will happen. Never rushes, never buries the risk, never
    bundles multiple actions. One risky action = one prompt = one yes.

    This does not read input — it only composes the message — so it is trivially
    testable and so the caller controls how it's displayed.
    """
    return (
        "I need to check with you before I do this.\n\n"
        f"What I would do: {human_description.strip()}\n\n"
        f"Why I'm stopping: {decision.reason.strip()}\n\n"
        "If you want me to go ahead, please type the word  yes  and press Enter.\n"
        "Anything else — or just pressing Enter — means no, and I will stop. "
        "I will never be upset about stopping."
    )


@dataclass
class ConfirmationResult:
    """Outcome of asking the person to confirm one risky action."""

    approved: bool
    # What the person actually typed (trimmed), for narration/logging. Empty for
    # a bare Enter. Never used to re-interpret the decision — `approved` is final.
    raw_response: str = ""


def confirm_risky_action(
    decision: ActionDecision,
    human_description: str,
    *,
    read_input: Callable[[str], str] | None = None,
    write_output: Callable[[str], None] | None = None,
) -> ConfirmationResult:
    """Run the informed-confirmation flow for ONE risky action (SAFETY.md §5).

    This is the contract the builder MUST use instead of writing their own
    prompt. It enforces, in one place:

    - **BLOCKED is terminal.** A ``Risk.BLOCKED`` decision can never be
      confirmed or unblocked. Calling this on a BLOCKED action always returns
      ``approved=False`` and never even asks — there is no yes that proceeds.
    - **ROUTINE needs no confirmation.** Passing a ROUTINE decision here is a
      programming error (the gate path should not ask); we fail loud rather
      than silently approve.
    - **Informed.** It shows ``build_confirmation_prompt(decision, ...)`` first,
      so the person sees, in plain language, exactly what will happen and why.
    - **Typed `yes` only.** Acceptance uses :func:`is_affirmative`: only the
      full word ``yes`` approves. Empty / bare Enter / "y" / anything else = no.
    - **One action = one yes.** There is no "approve all"; each call confirms
      exactly one action.

    I/O is injectable: pass ``read_input`` (like :func:`input`, takes the prompt
    string, returns the typed line) and ``write_output`` (like :func:`print`).
    Defaults wire to the real terminal, so production callers can omit them and
    tests can pass fakes with no real stdin.
    """
    if read_input is None:
        read_input = input
    if write_output is None:
        write_output = print

    if decision.risk is Risk.ROUTINE:
        raise ValueError(
            "confirm_risky_action called on a ROUTINE action. Routine actions "
            "must not be sent through confirmation; only RISKY actions are "
            "confirmed, and BLOCKED actions are never confirmed."
        )

    if decision.risk is Risk.BLOCKED:
        # Terminal. Never ask, never approve. Explain plainly and stop.
        write_output(
            "I can't do this one, and there's no way to turn that off.\n\n"
            f"What I was asked to do: {human_description.strip()}\n\n"
            f"Why: {decision.reason.strip()}"
        )
        return ConfirmationResult(approved=False, raw_response="")

    # RISKY: show the informed prompt, then read exactly one answer.
    write_output(build_confirmation_prompt(decision, human_description))
    try:
        raw = read_input("Type yes to go ahead, or press Enter to stop: ")
    except (EOFError, KeyboardInterrupt):
        # No real input / interrupted = stop. A missing answer is never a yes.
        return ConfirmationResult(approved=False, raw_response="")

    raw = raw if raw is not None else ""
    return ConfirmationResult(approved=is_affirmative(raw), raw_response=raw.strip())


# ---------------------------------------------------------------------------
# The single safe entry contract for the actor (M2-PLAN §"Where the gate sits").
#
# The builder's gated executor calls THIS to learn: is this action allowed, and
# if it's risky, was it informed-confirmed? There is no other sanctioned path to
# decide whether the mouse/keyboard may move. This function does NOT touch the
# hardware — the builder still owns execution — it owns the *decision*.
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    """The gate's verdict the builder acts on.

    ``allowed`` is the single boolean the actor checks: if False, do NOT touch
    the mouse/keyboard for this action — safe-stop. ``decision`` carries the
    classification (and plain-language ``reason``) for narration.
    """

    allowed: bool
    decision: ActionDecision


def gate_action(
    human_description: str,
    *,
    read_input: Callable[[str], str] | None = None,
    write_output: Callable[[str], None] | None = None,
) -> GateResult:
    """Single choke point: may this one action proceed? (SAFETY.md §1, §5.)

    The builder's ``gated_execute`` MUST call this and refuse to act unless
    ``GateResult.allowed`` is True. It is the *only* sanctioned way to decide
    whether an action reaches the actor:

    1. Classify the action with :func:`classify_action`.
    2. ``ROUTINE`` → allowed, no questions asked (narrate, then act).
    3. ``RISKY`` → run :func:`confirm_risky_action`; allowed only if the person
       typed an informed ``yes``.
    4. ``BLOCKED`` → never allowed; :func:`confirm_risky_action` is still called
       so the person hears the plain-language reason, but it can never approve.

    One call = one action = at most one yes. There is no batching and no
    "approve all". I/O is injectable for testing (see
    :func:`confirm_risky_action`).

    This function does not move the mouse or keyboard. It returns a verdict; the
    builder executes only when ``allowed`` is True, through the private actor
    primitive that nothing else may call.
    """
    decision = classify_action(human_description)

    if decision.risk is Risk.ROUTINE:
        return GateResult(allowed=True, decision=decision)

    confirmation = confirm_risky_action(
        decision,
        human_description,
        read_input=read_input,
        write_output=write_output,
    )
    return GateResult(allowed=confirmation.approved, decision=decision)
