// The scam shield for web pages (docs/SAFETY.md §2).
//
// Pure functions, no browser APIs, so the same file runs in the content script
// and in the unit tests. Everything here runs on the person's own computer:
// no page text leaves the browser for the shield to work.
//
// How this differs from the Mac app's shield (src/grandson/safety.py): that one
// fires on any single keyword, which is right for a one-off screen narration.
// A browser shield looks at every page all day, so a single word like "gift
// card" or "bitcoin" must not raise an alarm, or people learn to ignore it.
// Here each rule has STRONG patterns (phrases scammers use and honest pages
// rarely do) and WEAK ones (words that only matter in combination). The page
// is interrupted only when the signals add up.

export const LEVEL = { NONE: "none", CAUTION: "caution", DANGER: "danger" };

const STRONG = 3;
const WEAK = 1;

// Each rule: id, short label, a plain-language reason (SAFETY.md §4), and
// patterns. Patterns run against lower-cased text with URLs blanked out.
export const RULES = [
  {
    id: "fake-virus",
    label: "fake virus warning",
    reason:
      "It says your computer has a virus or is locked. Real virus warnings never appear on a web page like this.",
    strong: [
      /your (computer|pc|mac|device|system|iphone|ipad|phone|browser) (is|has been|may be|might be|was) (infected|hacked|compromised|locked|blocked|at risk|damaged)/,
      /\b(virus(es)?|malware|spyware|trojans?|threats?) (was |were |have been |has been )?(detected|found)\b/,
      /\b\d+ (virus(es)?|threats?|infections?) (detected|found)\b/,
      /\bdo not (turn off|restart|shut down|close) (your (computer|pc|mac)|this (window|page|tab))\b/,
      /\byour (personal |private )?(data|files|photos|information|passwords?) (is|are) (being stolen|at risk|in danger|exposed)\b/,
    ],
    weak: [
      /\btrojan\b/,
      /\bspyware\b/,
      /\bsecurity (alert|warning)\b/,
      /\bcritical (alert|warning|error)\b/,
      /\bsystem (warning|alert)\b/,
    ],
  },
  {
    id: "phone-number",
    label: "pushing you to call a phone number",
    reason:
      "It is pushing you to phone a number shown on the page. That number reaches the scammers, not a real company.",
    strong: [
      /call (us |now |immediately |this number |our )?(toll[- ]?free )?(at |on )?\+?\d[\d\-\s().]{6,}/,
      /call (microsoft|apple|amazon|windows|google|paypal|norton|mcafee) (support|security|help)/,
      /call (the |our )?(support|help ?line|technician|number) (now|immediately|right away)/,
      /contact (microsoft|apple|amazon|windows) support (immediately|now)/,
      /\+?\d[\d\-\s().]{6,}\s*to (secure|verify|unlock|reactivate|restore|protect|confirm) your (account|id|identity|computer)\b/,
    ],
    weak: [/\b(toll[- ]?free|help ?line|helpdesk)\b/],
  },
  {
    id: "impersonation",
    label: "pretending to be a big company",
    reason:
      "It claims to be from a big company like Microsoft, Apple, or Amazon and says something is wrong with your account. Those companies do not contact you this way.",
    strong: [
      /your (microsoft|apple|amazon|icloud|paypal|netflix|google|facebook|bank) (id |account )?(has been|is|was|will be) (suspended|locked|compromised|disabled|restricted|closed)/,
      /\bapple id\b.{0,40}\b(locked|suspended|disabled|compromised|restricted)\b/,
      /\bverify your (account|identity|payment (details|information)) (immediately|now|to avoid|within)\b/,
      /\bunusual (sign[- ]?in|activity|login)\b.{0,60}\b(verify|confirm|call)\b/,
    ],
    weak: [
      /(microsoft|apple|amazon|windows|norton|mcafee|geek squad).{0,30}(support|security|technician|help ?desk|service team)/,
      /\bwindows defender\b/,
    ],
  },
  {
    id: "remote-access",
    label: "asking to control your computer",
    reason:
      "It wants you to install a program that lets a stranger control your computer from far away. They could then see and take everything.",
    strong: [
      /\b(download|install|open|run|launch)\b.{0,30}\b(anydesk|teamviewer|team viewer|logmein|ultraviewer|quick ?assist|screenconnect)\b/,
      /\b(let|allow|give) (us|me|them|our technicians?) (to )?(access|control|connect|remote)/,
      /\bso (i|we) can (access|connect to|control|fix) your (computer|screen|pc|mac|device)\b/,
      /\bgrant (us |me )?(remote )?access\b/,
    ],
    weak: [
      /\b(anydesk|teamviewer|team viewer|logmein|ultraviewer|quick ?assist|screenconnect)\b/,
      /\bremote (access|desktop|connection|support|control)\b/,
    ],
  },
  {
    id: "pressure",
    label: "rushing you or asking for secrecy",
    reason:
      "It is rushing you or telling you to keep it secret. Honest help never works that way. Pressure and secrecy are how scams trap people.",
    strong: [
      /\bdo not (tell|talk to|inform) (anyone|your family|the bank|anybody|your (son|daughter|children|kids))\b/,
      /\bdon'?t tell (anyone|your family|anybody|the bank)\b/,
      /\bkeep this (a )?(secret|confidential|between us)\b/,
      /\b(final|last) (warning|notice|chance)\b/,
      /\b(account|access|computer|device) (will be|is about to be) (suspended|closed|locked|deleted|terminated|disabled)\b/,
    ],
    weak: [
      /\bact (now|fast|immediately)\b/,
      /\b(in|within|you have) \d+ (minutes?|hours?|seconds?)\b/,
      /\bimmediate action (is )?required\b/,
      /\burgent(ly)?\b/,
      /\bexpires? (in|within|today|soon)\b/,
    ],
  },
  {
    id: "odd-payment",
    label: "asking for gift cards or unusual payment",
    reason:
      "It asks to be paid with gift cards, a wire transfer, or digital coins like Bitcoin. No real company or government office is paid that way.",
    strong: [
      /\b(pay|payment|paid|settle)\b.{0,30}\b(with|using|by|in|via)\b.{0,20}\b(gift ?cards?|bitcoin|crypto(currency)?|wire transfer|western union|moneygram)\b/,
      /\b(buy|purchase|get)\b.{0,25}\bgift ?cards?\b.{0,60}\b(send|read|scratch|share|give|tell)\b/,
      /\b(code|numbers?|pin) on the back of the (gift )?cards?\b/,
      /\bpay (a |the )?(fee|fine|tax|charge) (to|in order to) (release|unlock|claim|receive)\b/,
      /\bsend (the )?(money|payment|funds|bitcoin) (now|immediately|today)\b/,
    ],
    weak: [
      /\bgift ?cards?\b/,
      /\bwire (transfer|the money|funds)\b/,
      /\b(bitcoin|btc|crypto(currency)?|ethereum|usdt)\b/,
      /\bmoney ?gram\b/,
      /\bwestern union\b/,
    ],
  },
  {
    id: "prize",
    label: "a prize or inheritance you never expected",
    reason:
      "It says you won money or were left an inheritance. These are made up to get your details or a 'fee' out of you.",
    strong: [
      /\byou('ve| have)? (just )?won\b/,
      /\b(congratulations|congrats).{0,40}(won|winner|selected|prize)\b/,
      /\b(claim|collect) your (prize|reward|winnings|inheritance|gift)\b/,
      /\byou (have been|were|are) (selected|chosen)\b.{0,40}\b(prize|reward|gift|winner|iphone|voucher)\b/,
      /\bunclaimed (funds|money|inheritance)\b/,
      /\bbeneficiary of (a |an )?(fund|estate|sum)\b/,
    ],
    weak: [
      /\b(lottery|sweepstakes|jackpot|grand prize)\b/,
      /\binheritance\b/,
      /\bmillion (dollars|usd|pounds|euros)\b/,
      /\b(lucky )?winner\b/,
    ],
  },
  {
    id: "refund",
    label: "a refund or charge you did not expect",
    reason:
      "It says you are owed a refund or were charged for something. This trick gets people to phone the scammers or share bank details.",
    strong: [
      /\bto (cancel|dispute|stop) (this |the |your )?(charge|order|renewal|subscription|payment),? (please )?(call|contact|phone)\b/,
      /\byour (subscription|renewal|order) (has been|will be|was) (charged|renewed|billed|auto[- ]?renewed)\b.{0,80}\b(refund|cancel|call)\b/,
      /\b(send|pay|return|transfer) (back |us )?the (difference|extra|overpayment|excess)\b/,
      /\bwe (have )?(accidentally|mistakenly) (refunded|sent|transferred)\b/,
    ],
    weak: [
      /\b(due|owed|entitled to) a refund\b/,
      /\bover ?(paid|payment|charged)\b/,
      /\b(geek squad|norton|mcafee|paypal) .{0,30}(renewal|invoice|charge)\b/,
    ],
  },
  {
    id: "romance",
    label: "someone online asking for money",
    reason:
      "Someone you met online is asking for money. This is a common and painful scam.",
    strong: [
      /\b(my (love|dear|darling|honey))\b.{0,60}\b(money|funds|gift cards?|bitcoin)\b/,
      /\b(stuck|stranded) (abroad|overseas|in another country)\b.{0,80}\b(money|send|wire|help)\b/,
      /\bi (love|need) you\b.{0,40}\b(money|gift cards?|western union|bitcoin)\b/,
    ],
    weak: [],
  },
];

const URL_RE = /https?:\/\/[^\s)>\]"']+/gi;
// Words that show up when a page is ABOUT scams (news, advice, a bank's safety
// page) rather than being one. Scam pages do not call themselves scams.
const EDUCATIONAL_RE = /\b(scams?|scammers?|fraud(sters?|ulent)?|phishing|con artists?|swindl\w+)\b/g;

// Brands scammers imitate in web addresses. Generic words ("bank", "windows")
// are left out on purpose: they appear in too many honest addresses.
export const BRANDS = [
  "apple", "icloud", "microsoft", "amazon", "paypal", "google", "netflix",
  "facebook", "instagram", "whatsapp", "wellsfargo", "chase", "citibank",
  "bankofamerica", "norton", "mcafee", "usps", "fedex", "ups", "dhl", "irs",
  "medicare", "walmart", "ebay", "venmo", "zelle", "coinbase",
];

const CC_SLD = new Set(["co", "com", "org", "net", "gov", "edu", "ac"]);
const LEET = { 0: "o", 1: "l", 3: "e", 4: "a", 5: "s", 7: "t" };

export function hostOf(url) {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
}

/** Split a host into [labels left of the registrable name, registrable label]. */
function splitHost(host) {
  const labels = host.split(".").filter(Boolean);
  if (labels.length < 2) return { sub: [], registrable: labels[0] || "" };
  const suffixLen =
    labels.length >= 3 && CC_SLD.has(labels[labels.length - 2]) ? 2 : 1;
  const idx = labels.length - 1 - suffixLen;
  return { sub: labels.slice(0, idx), registrable: labels[idx] };
}

/** "example.co.uk" for "a.b.example.co.uk": the part someone actually owns. */
export function registrableDomain(host) {
  const labels = host.split(".").filter(Boolean);
  if (labels.length <= 2) return labels.join(".");
  const suffixLen = CC_SLD.has(labels[labels.length - 2]) ? 2 : 1;
  return labels.slice(-(suffixLen + 1)).join(".");
}

const deleet = (s) => s.replace(/[013457]/g, (c) => LEET[c]);

/**
 * Return the brand a web address is imitating, or "" if it looks honest.
 *
 * Matching is by whole word (label or hyphen-separated token), never by
 * substring, so "purchase.example.com" does not count as imitating "chase".
 *   apple.security-check.com -> "apple"   (brand in front of someone else's site)
 *   usps-redelivery.com      -> "usps"    (brand glued onto another name)
 *   amaz0n.com               -> "amazon"  (letters swapped for digits)
 *   support.apple.com        -> ""        (really Apple)
 */
export function impersonatedBrand(host) {
  if (!host || /^\d{1,3}(\.\d{1,3}){3}$/.test(host)) return "";
  const { sub, registrable } = splitHost(host);
  if (!registrable) return "";
  if (BRANDS.includes(registrable)) return "";

  // Compare whole words, both as written and with digit-for-letter swaps undone.
  const words = (label) => {
    const plain = deleet(label);
    return [...label.split(/[-_]/), ...(plain !== label ? [plain, ...plain.split(/[-_]/)] : [])];
  };
  const regWords = words(registrable);
  const subWords = sub.flatMap(words);
  for (const brand of BRANDS) {
    if (subWords.includes(brand) || regWords.includes(brand)) return brand;
  }
  return "";
}

const DOMAIN_IN_TEXT_RE =
  /\b((?:[a-z0-9-]+\.)+(?:com|org|net|gov|edu|co\.uk|org\.uk|gov\.uk|ca|com\.au|us|io))\b/i;

/**
 * Check the links on a page. `links` is [{ text, href }].
 * Links are only ever a WEAK signal: honest newsletters route links through
 * tracking addresses all the time, so a mismatch alone proves nothing.
 */
export function scanLinks(links, pageHost = "") {
  const findings = [];
  const pageDomain = registrableDomain(pageHost);
  let lookalike = "";
  let mismatch = null;
  let numeric = "";

  for (const { text = "", href = "" } of links || []) {
    if (!/^https?:/i.test(href)) continue;
    const host = hostOf(href);
    if (!host) continue;
    const domain = registrableDomain(host);
    if (domain === pageDomain) continue;

    if (!numeric && /^\d{1,3}(\.\d{1,3}){3}$/.test(host)) numeric = host;
    if (!lookalike) {
      const brand = impersonatedBrand(host);
      if (brand) lookalike = `${brand}|${host}`;
    }
    if (!mismatch) {
      const m = DOMAIN_IN_TEXT_RE.exec(text.trim());
      if (m) {
        const shown = registrableDomain(m[1].toLowerCase().replace(/^www\./, ""));
        if (shown && shown !== domain) mismatch = { shown, actual: host };
      }
    }
  }

  if (lookalike) {
    const [brand, host] = lookalike.split("|");
    findings.push({
      id: "lookalike-link",
      label: "a link that imitates a real company",
      reason: `A link here uses the name "${brand}" but really goes to "${host}", which is not the real ${brand} website.`,
      weight: WEAK,
      strong: false,
    });
  }
  if (mismatch) {
    findings.push({
      id: "mismatched-link",
      label: "a link that goes somewhere else than it says",
      reason: `A link here says "${mismatch.shown}" but really goes to "${mismatch.actual}".`,
      weight: WEAK,
      strong: false,
    });
  }
  if (numeric) {
    findings.push({
      id: "numeric-link",
      label: "a link to a web address made of numbers",
      reason: `A link here goes to "${numeric}". Real companies use a normal website name, not a string of numbers.`,
      weight: WEAK,
      strong: false,
    });
  }
  return findings;
}

/**
 * Scan one page.
 *
 * input: {
 *   text:   visible page text,
 *   url:    the page's address,
 *   links:  [{ text, href }],
 *   fields: { password: bool, card: bool }   // does the page ask for these?
 * }
 * returns { level, score, findings: [{ id, label, reason, strong }], educational }
 */
export function scanPage({ text = "", url = "", links = [], fields = {} } = {}) {
  const findings = [];
  const host = hostOf(url);
  const lower = String(text).toLowerCase().replace(URL_RE, " ");

  for (const rule of RULES) {
    const strong = rule.strong.some((re) => re.test(lower));
    const weak = !strong && rule.weak.some((re) => re.test(lower));
    if (strong || weak) {
      findings.push({
        id: rule.id,
        label: rule.label,
        reason: rule.reason,
        weight: strong ? STRONG : WEAK,
        strong,
      });
    }
  }

  // The page's own address imitating a brand is a strong sign by itself.
  const brand = impersonatedBrand(host);
  if (brand) {
    findings.push({
      id: "lookalike-site",
      label: "a web address that imitates a real company",
      reason: `This page uses the name "${brand}", but its real address is "${host}". That is not the real ${brand} website.`,
      weight: STRONG,
      strong: true,
    });
  }

  const asksForSecrets = Boolean(fields.password || fields.card);
  if (asksForSecrets && /^http:/i.test(url) && !/^http:\/\/(localhost|127\.)/i.test(url)) {
    findings.push({
      id: "insecure-form",
      label: "asking for private details without a secure connection",
      reason:
        "This page asks for a password or card number, but it is not using a secure connection. Honest websites always do.",
      weight: 2,
      strong: false,
    });
  }

  findings.push(...scanLinks(links, host));

  const score = findings.reduce((sum, f) => sum + f.weight, 0);
  const strongCount = findings.filter((f) => f.strong).length;

  let level = LEVEL.NONE;
  if (strongCount >= 2 || (strongCount >= 1 && score >= 5)) level = LEVEL.DANGER;
  else if (strongCount >= 1 || score >= 4) level = LEVEL.CAUTION;

  // A fake login page: imitates a brand AND asks for a password or card.
  if (brand && asksForSecrets) level = LEVEL.DANGER;

  // A page that talks ABOUT scams (news, advice) uses the same phrases as a
  // real one. Step it down one notch so advice articles do not get a red
  // banner. A copycat address asking for secrets is never stepped down.
  const educational = (lower.match(EDUCATIONAL_RE) || []).length >= 3;
  if (educational && !(brand && asksForSecrets)) {
    if (level === LEVEL.DANGER) level = LEVEL.CAUTION;
    else if (level === LEVEL.CAUTION) level = LEVEL.NONE;
  }

  findings.sort((a, b) => b.weight - a.weight);
  return {
    level,
    score,
    educational,
    findings: findings.map(({ id, label, reason, strong }) => ({ id, label, reason, strong })),
  };
}
