import test from "node:test";
import assert from "node:assert/strict";
import {
  scanPage,
  scanLinks,
  impersonatedBrand,
  registrableDomain,
  LEVEL,
} from "../src/scam-rules.js";

const level = (input) => scanPage(input).level;

// ---- Real scams must raise the red banner ---------------------------------

test("fake virus popup with a phone number is DANGER", () => {
  const r = scanPage({
    url: "https://secure-pc-alert.example.net/warning",
    text: `Microsoft Security Alert! Your computer is infected with 3 viruses.
      Do not turn off your computer. Call Microsoft Support now at 1-888-555-0142.`,
  });
  assert.equal(r.level, LEVEL.DANGER);
  assert.ok(r.findings.some((f) => f.id === "fake-virus"));
  assert.ok(r.findings.some((f) => f.id === "phone-number"));
});

test("gift card payment demand with secrecy is DANGER", () => {
  assert.equal(
    level({
      url: "https://example.org/notice",
      text: `Final notice. To avoid arrest you must pay the fine using gift cards.
        Buy three Google Play gift cards and read us the numbers. Do not tell anyone.`,
    }),
    LEVEL.DANGER,
  );
});

test("prize scam asking for a release fee is DANGER", () => {
  assert.equal(
    level({
      url: "https://winners.example.com",
      text: "Congratulations! You have won $2,500,000 in the international lottery. Pay a fee to release your winnings. Act now, offer expires today.",
    }),
    LEVEL.DANGER,
  );
});

test("refund scam that wants remote access is DANGER", () => {
  assert.equal(
    level({
      url: "https://example.com/invoice",
      text: "Your subscription has been renewed for $399.99. To cancel this charge, call our helpline. Our technician will ask you to install AnyDesk so we can connect to your computer.",
    }),
    LEVEL.DANGER,
  );
});

test("copycat login page is DANGER even with innocent text", () => {
  const r = scanPage({
    url: "https://paypa1-login.example.com/signin",
    text: "Log in to your account. Email. Password. Forgot password?",
    fields: { password: true },
  });
  assert.equal(r.level, LEVEL.DANGER);
  assert.equal(r.findings[0].id, "lookalike-site");
});

test("locked Apple ID message on a copycat address is DANGER", () => {
  assert.equal(
    level({
      url: "https://apple.id-verify-support.com/",
      text: "Your Apple ID has been locked for security reasons. Verify your account now to avoid suspension.",
      fields: { password: true },
    }),
    LEVEL.DANGER,
  );
});

// ---- Honest pages must NOT be interrupted ---------------------------------

test("a shop selling gift cards is clear", () => {
  assert.equal(
    level({
      url: "https://www.amazon.com/gift-cards",
      text: "Gift cards. Send an eGift card by email. Offer expires in 30 days. Amazon gift cards never expire.",
    }),
    LEVEL.NONE,
  );
});

test("a news story about bitcoin is clear", () => {
  assert.equal(
    level({
      url: "https://www.bbc.co.uk/news/business",
      text: "Bitcoin rose 4% today as cryptocurrency markets rallied. Analysts say the move was urgent for investors watching the lottery of tech stocks.",
    }),
    LEVEL.NONE,
  );
});

test("a real bank login page is clear", () => {
  assert.equal(
    level({
      url: "https://secure.chase.com/login",
      text: "Sign in. Username. Password. Remember me. Forgot username or password?",
      fields: { password: true },
    }),
    LEVEL.NONE,
  );
});

test("an advice article ABOUT scams is not a red banner", () => {
  const r = scanPage({
    url: "https://consumer.ftc.gov/articles/tech-support-scams",
    text: `How to spot tech support scams. Scammers may show a pop-up saying your
      computer is infected and tell you to call a phone number. Scammers often ask
      you to pay with gift cards or a wire transfer, and to keep this secret.
      Never give remote access to someone who contacts you. Report fraud to the FTC.`,
  });
  assert.equal(r.educational, true);
  assert.notEqual(r.level, LEVEL.DANGER);
});

test("a single weak word does nothing", () => {
  assert.equal(level({ url: "https://example.com", text: "Security alert settings and remote desktop help." }), LEVEL.NONE);
});

test("one strong sign alone is only a CAUTION, not a red banner", () => {
  assert.equal(
    level({ url: "https://example.com", text: "Congratulations to Maria, who won the baking prize this year!" }),
    LEVEL.CAUTION,
  );
});

test("empty input is clear", () => {
  assert.equal(scanPage().level, LEVEL.NONE);
  assert.equal(scanPage({ text: "", url: "" }).level, LEVEL.NONE);
});

// ---- Web address checks ---------------------------------------------------

test("impersonatedBrand spots copycats", () => {
  assert.equal(impersonatedBrand("apple.security-check.com"), "apple");
  assert.equal(impersonatedBrand("usps-redelivery.com"), "usps");
  assert.equal(impersonatedBrand("amaz0n.com"), "amazon");
  assert.equal(impersonatedBrand("paypa1.com"), "paypal");
  assert.equal(impersonatedBrand("secure-paypal.co.uk"), "paypal");
});

test("impersonatedBrand leaves real and unrelated sites alone", () => {
  for (const host of [
    "apple.com", "support.apple.com", "amazon.co.uk", "smile.amazon.com",
    "purchase.example.com", "amazonaws.com", "bankofamerica.com",
    "chase.com", "upstate.example.org", "example.com", "192.168.1.1", "localhost",
  ]) {
    assert.equal(impersonatedBrand(host), "", host);
  }
});

test("registrableDomain", () => {
  assert.equal(registrableDomain("a.b.example.com"), "example.com");
  assert.equal(registrableDomain("shop.example.co.uk"), "example.co.uk");
  assert.equal(registrableDomain("example.com"), "example.com");
});

test("scanLinks flags a link that says one site and goes to another", () => {
  const f = scanLinks([{ text: "www.paypal.com", href: "https://evil.example.net/x" }], "mail.example.org");
  assert.ok(f.some((x) => x.id === "mismatched-link"));
});

test("scanLinks ignores links within the same site and plain-text links", () => {
  assert.deepEqual(
    scanLinks(
      [
        { text: "example.com", href: "https://shop.example.com/a" },
        { text: "Click here", href: "https://other.example.net/" },
        { text: "mail us", href: "mailto:a@b.c" },
      ],
      "www.example.com",
    ),
    [],
  );
});

test("links alone never raise a red banner", () => {
  assert.notEqual(
    level({
      url: "https://mail.example.org/inbox",
      text: "Your weekly newsletter",
      links: [
        { text: "paypal.com", href: "https://click.tracker-mail.net/1" },
        { text: "x", href: "http://203.0.113.9/a" },
      ],
    }),
    LEVEL.DANGER,
  );
});

test("password form on a plain http page adds a warning sign", () => {
  const r = scanPage({ url: "http://example.com/login", text: "Password", fields: { password: true } });
  assert.ok(r.findings.some((f) => f.id === "insecure-form"));
});
