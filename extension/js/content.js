(() => {
  // src/scam-rules.js
  var LEVEL = { NONE: "none", CAUTION: "caution", DANGER: "danger" };
  var STRONG = 3;
  var WEAK = 1;
  var RULES = [
    {
      id: "fake-virus",
      label: "fake virus warning",
      reason: "It says your computer has a virus or is locked. Real virus warnings never appear on a web page like this.",
      strong: [
        /your (computer|pc|mac|device|system|iphone|ipad|phone|browser) (is|has been|may be|might be|was) (infected|hacked|compromised|locked|blocked|at risk|damaged)/,
        /\b(virus(es)?|malware|spyware|trojans?|threats?) (was |were |have been |has been )?(detected|found)\b/,
        /\b\d+ (virus(es)?|threats?|infections?) (detected|found)\b/,
        /\bdo not (turn off|restart|shut down|close) (your (computer|pc|mac)|this (window|page|tab))\b/,
        /\byour (personal |private )?(data|files|photos|information|passwords?) (is|are) (being stolen|at risk|in danger|exposed)\b/
      ],
      weak: [
        /\btrojan\b/,
        /\bspyware\b/,
        /\bsecurity (alert|warning)\b/,
        /\bcritical (alert|warning|error)\b/,
        /\bsystem (warning|alert)\b/
      ]
    },
    {
      id: "phone-number",
      label: "pushing you to call a phone number",
      reason: "It is pushing you to phone a number shown on the page. That number reaches the scammers, not a real company.",
      strong: [
        /call (us |now |immediately |this number |our )?(toll[- ]?free )?(at |on )?\+?\d[\d\-\s().]{6,}/,
        /call (microsoft|apple|amazon|windows|google|paypal|norton|mcafee) (support|security|help)/,
        /call (the |our )?(support|help ?line|technician|number) (now|immediately|right away)/,
        /contact (microsoft|apple|amazon|windows) support (immediately|now)/,
        /\+?\d[\d\-\s().]{6,}\s*to (secure|verify|unlock|reactivate|restore|protect|confirm) your (account|id|identity|computer)\b/
      ],
      weak: [/\b(toll[- ]?free|help ?line|helpdesk)\b/]
    },
    {
      id: "impersonation",
      label: "pretending to be a big company",
      reason: "It claims to be from a big company like Microsoft, Apple, or Amazon and says something is wrong with your account. Those companies do not contact you this way.",
      strong: [
        /your (microsoft|apple|amazon|icloud|paypal|netflix|google|facebook|bank) (id |account )?(has been|is|was|will be) (suspended|locked|compromised|disabled|restricted|closed)/,
        /\bapple id\b.{0,40}\b(locked|suspended|disabled|compromised|restricted)\b/,
        /\bverify your (account|identity|payment (details|information)) (immediately|now|to avoid|within)\b/,
        /\bunusual (sign[- ]?in|activity|login)\b.{0,60}\b(verify|confirm|call)\b/
      ],
      weak: [
        /(microsoft|apple|amazon|windows|norton|mcafee|geek squad).{0,30}(support|security|technician|help ?desk|service team)/,
        /\bwindows defender\b/
      ]
    },
    {
      id: "remote-access",
      label: "asking to control your computer",
      reason: "It wants you to install a program that lets a stranger control your computer from far away. They could then see and take everything.",
      strong: [
        /\b(download|install|open|run|launch)\b.{0,30}\b(anydesk|teamviewer|team viewer|logmein|ultraviewer|quick ?assist|screenconnect)\b/,
        /\b(let|allow|give) (us|me|them|our technicians?) (to )?(access|control|connect|remote)/,
        /\bso (i|we) can (access|connect to|control|fix) your (computer|screen|pc|mac|device)\b/,
        /\bgrant (us |me )?(remote )?access\b/
      ],
      weak: [
        /\b(anydesk|teamviewer|team viewer|logmein|ultraviewer|quick ?assist|screenconnect)\b/,
        /\bremote (access|desktop|connection|support|control)\b/
      ]
    },
    {
      id: "pressure",
      label: "rushing you or asking for secrecy",
      reason: "It is rushing you or telling you to keep it secret. Honest help never works that way. Pressure and secrecy are how scams trap people.",
      strong: [
        /\bdo not (tell|talk to|inform) (anyone|your family|the bank|anybody|your (son|daughter|children|kids))\b/,
        /\bdon'?t tell (anyone|your family|anybody|the bank)\b/,
        /\bkeep this (a )?(secret|confidential|between us)\b/,
        /\b(final|last) (warning|notice|chance)\b/,
        /\b(account|access|computer|device) (will be|is about to be) (suspended|closed|locked|deleted|terminated|disabled)\b/
      ],
      weak: [
        /\bact (now|fast|immediately)\b/,
        /\b(in|within|you have) \d+ (minutes?|hours?|seconds?)\b/,
        /\bimmediate action (is )?required\b/,
        /\burgent(ly)?\b/,
        /\bexpires? (in|within|today|soon)\b/
      ]
    },
    {
      id: "odd-payment",
      label: "asking for gift cards or unusual payment",
      reason: "It asks to be paid with gift cards, a wire transfer, or digital coins like Bitcoin. No real company or government office is paid that way.",
      strong: [
        /\b(pay|payment|paid|settle)\b.{0,30}\b(with|using|by|in|via)\b.{0,20}\b(gift ?cards?|bitcoin|crypto(currency)?|wire transfer|western union|moneygram)\b/,
        /\b(buy|purchase|get)\b.{0,25}\bgift ?cards?\b.{0,60}\b(send|read|scratch|share|give|tell)\b/,
        /\b(code|numbers?|pin) on the back of the (gift )?cards?\b/,
        /\bpay (a |the )?(fee|fine|tax|charge) (to|in order to) (release|unlock|claim|receive)\b/,
        /\bsend (the )?(money|payment|funds|bitcoin) (now|immediately|today)\b/
      ],
      weak: [
        /\bgift ?cards?\b/,
        /\bwire (transfer|the money|funds)\b/,
        /\b(bitcoin|btc|crypto(currency)?|ethereum|usdt)\b/,
        /\bmoney ?gram\b/,
        /\bwestern union\b/
      ]
    },
    {
      id: "prize",
      label: "a prize or inheritance you never expected",
      reason: "It says you won money or were left an inheritance. These are made up to get your details or a 'fee' out of you.",
      strong: [
        /\byou('ve| have)? (just )?won\b/,
        /\b(congratulations|congrats).{0,40}(won|winner|selected|prize)\b/,
        /\b(claim|collect) your (prize|reward|winnings|inheritance|gift)\b/,
        /\byou (have been|were|are) (selected|chosen)\b.{0,40}\b(prize|reward|gift|winner|iphone|voucher)\b/,
        /\bunclaimed (funds|money|inheritance)\b/,
        /\bbeneficiary of (a |an )?(fund|estate|sum)\b/
      ],
      weak: [
        /\b(lottery|sweepstakes|jackpot|grand prize)\b/,
        /\binheritance\b/,
        /\bmillion (dollars|usd|pounds|euros)\b/,
        /\b(lucky )?winner\b/
      ]
    },
    {
      id: "refund",
      label: "a refund or charge you did not expect",
      reason: "It says you are owed a refund or were charged for something. This trick gets people to phone the scammers or share bank details.",
      strong: [
        /\bto (cancel|dispute|stop) (this |the |your )?(charge|order|renewal|subscription|payment),? (please )?(call|contact|phone)\b/,
        /\byour (subscription|renewal|order) (has been|will be|was) (charged|renewed|billed|auto[- ]?renewed)\b.{0,80}\b(refund|cancel|call)\b/,
        /\b(send|pay|return|transfer) (back |us )?the (difference|extra|overpayment|excess)\b/,
        /\bwe (have )?(accidentally|mistakenly) (refunded|sent|transferred)\b/
      ],
      weak: [
        /\b(due|owed|entitled to) a refund\b/,
        /\bover ?(paid|payment|charged)\b/,
        /\b(geek squad|norton|mcafee|paypal) .{0,30}(renewal|invoice|charge)\b/
      ]
    },
    {
      id: "romance",
      label: "someone online asking for money",
      reason: "Someone you met online is asking for money. This is a common and painful scam.",
      strong: [
        /\b(my (love|dear|darling|honey))\b.{0,60}\b(money|funds|gift cards?|bitcoin)\b/,
        /\b(stuck|stranded) (abroad|overseas|in another country)\b.{0,80}\b(money|send|wire|help)\b/,
        /\bi (love|need) you\b.{0,40}\b(money|gift cards?|western union|bitcoin)\b/
      ],
      weak: []
    }
  ];
  var URL_RE = /https?:\/\/[^\s)>\]"']+/gi;
  var EDUCATIONAL_RE = /\b(scams?|scammers?|fraud(sters?|ulent)?|phishing|con artists?|swindl\w+)\b/g;
  var BRANDS = [
    "apple",
    "icloud",
    "microsoft",
    "amazon",
    "paypal",
    "google",
    "netflix",
    "facebook",
    "instagram",
    "whatsapp",
    "wellsfargo",
    "chase",
    "citibank",
    "bankofamerica",
    "norton",
    "mcafee",
    "usps",
    "fedex",
    "ups",
    "dhl",
    "irs",
    "medicare",
    "walmart",
    "ebay",
    "venmo",
    "zelle",
    "coinbase"
  ];
  var CC_SLD = /* @__PURE__ */ new Set(["co", "com", "org", "net", "gov", "edu", "ac"]);
  var LEET = { 0: "o", 1: "l", 3: "e", 4: "a", 5: "s", 7: "t" };
  function hostOf(url) {
    try {
      return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
    } catch {
      return "";
    }
  }
  function splitHost(host) {
    const labels = host.split(".").filter(Boolean);
    if (labels.length < 2) return { sub: [], registrable: labels[0] || "" };
    const suffixLen = labels.length >= 3 && CC_SLD.has(labels[labels.length - 2]) ? 2 : 1;
    const idx = labels.length - 1 - suffixLen;
    return { sub: labels.slice(0, idx), registrable: labels[idx] };
  }
  function registrableDomain(host) {
    const labels = host.split(".").filter(Boolean);
    if (labels.length <= 2) return labels.join(".");
    const suffixLen = CC_SLD.has(labels[labels.length - 2]) ? 2 : 1;
    return labels.slice(-(suffixLen + 1)).join(".");
  }
  var deleet = (s) => s.replace(/[013457]/g, (c) => LEET[c]);
  function impersonatedBrand(host) {
    if (!host || /^\d{1,3}(\.\d{1,3}){3}$/.test(host)) return "";
    const { sub, registrable } = splitHost(host);
    if (!registrable) return "";
    if (BRANDS.includes(registrable)) return "";
    const words = (label) => {
      const plain = deleet(label);
      return [...label.split(/[-_]/), ...plain !== label ? [plain, ...plain.split(/[-_]/)] : []];
    };
    const regWords = words(registrable);
    const subWords = sub.flatMap(words);
    for (const brand of BRANDS) {
      if (subWords.includes(brand) || regWords.includes(brand)) return brand;
    }
    return "";
  }
  var DOMAIN_IN_TEXT_RE = /\b((?:[a-z0-9-]+\.)+(?:com|org|net|gov|edu|co\.uk|org\.uk|gov\.uk|ca|com\.au|us|io))\b/i;
  function scanLinks(links, pageHost = "") {
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
        strong: false
      });
    }
    if (mismatch) {
      findings.push({
        id: "mismatched-link",
        label: "a link that goes somewhere else than it says",
        reason: `A link here says "${mismatch.shown}" but really goes to "${mismatch.actual}".`,
        weight: WEAK,
        strong: false
      });
    }
    if (numeric) {
      findings.push({
        id: "numeric-link",
        label: "a link to a web address made of numbers",
        reason: `A link here goes to "${numeric}". Real companies use a normal website name, not a string of numbers.`,
        weight: WEAK,
        strong: false
      });
    }
    return findings;
  }
  function scanPage({ text = "", url = "", links = [], fields = {} } = {}) {
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
          strong
        });
      }
    }
    const brand = impersonatedBrand(host);
    if (brand) {
      findings.push({
        id: "lookalike-site",
        label: "a web address that imitates a real company",
        reason: `This page uses the name "${brand}", but its real address is "${host}". That is not the real ${brand} website.`,
        weight: STRONG,
        strong: true
      });
    }
    const asksForSecrets = Boolean(fields.password || fields.card);
    if (asksForSecrets && /^http:/i.test(url) && !/^http:\/\/(localhost|127\.)/i.test(url)) {
      findings.push({
        id: "insecure-form",
        label: "asking for private details without a secure connection",
        reason: "This page asks for a password or card number, but it is not using a secure connection. Honest websites always do.",
        weight: 2,
        strong: false
      });
    }
    findings.push(...scanLinks(links, host));
    const score = findings.reduce((sum, f) => sum + f.weight, 0);
    const strongCount = findings.filter((f) => f.strong).length;
    let level = LEVEL.NONE;
    if (strongCount >= 2 || strongCount >= 1 && score >= 5) level = LEVEL.DANGER;
    else if (strongCount >= 1 || score >= 4) level = LEVEL.CAUTION;
    if (brand && asksForSecrets) level = LEVEL.DANGER;
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
      findings: findings.map(({ id, label, reason, strong }) => ({ id, label, reason, strong }))
    };
  }

  // src/content.js
  var SCAN_TEXT_LIMIT = 6e4;
  var SHARE_TEXT_LIMIT = 2e4;
  var RESCAN_GAP_MS = 2e3;
  var lastScan = { level: LEVEL.NONE, score: 0, findings: [] };
  var dismissed = false;
  var bannerHost = null;
  function pageText() {
    return (document.body?.innerText || "").replace(/\n{3,}/g, "\n\n");
  }
  function pageFields() {
    const card = 'input[autocomplete^="cc-"], input[name*="card" i][name*="num" i], input[id*="card" i][id*="num" i], input[name*="cvv" i], input[name*="cvc" i], input[placeholder*="card number" i]';
    return {
      password: Boolean(document.querySelector('input[type="password"]')),
      card: Boolean(document.querySelector(card))
    };
  }
  function pageLinks() {
    return Array.from(document.links).slice(0, 400).map((a) => ({ text: (a.innerText || "").slice(0, 120), href: a.href }));
  }
  function runScan() {
    lastScan = scanPage({
      text: pageText().slice(0, SCAN_TEXT_LIMIT),
      url: location.href,
      links: pageLinks(),
      fields: pageFields()
    });
    chrome.runtime.sendMessage({ type: "scan", result: lastScan }).catch(() => {
    });
    if (lastScan.level === LEVEL.DANGER && !dismissed) showBanner(lastScan);
    else if (lastScan.level !== LEVEL.DANGER) removeBanner();
  }
  function el(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    Object.assign(node, props);
    for (const child of children) node.append(child);
    return node;
  }
  function removeBanner() {
    bannerHost?.remove();
    bannerHost = null;
  }
  async function showBanner(scan) {
    if (bannerHost) return;
    const host = bannerHost = document.createElement("div");
    host.id = "grandson-scam-warning";
    const root = host.attachShadow({ mode: "closed" });
    let family = {};
    try {
      family = await chrome.storage.local.get(["familyName", "familyPhone"]) || {};
    } catch {
    }
    if (bannerHost !== host) return;
    const style = el("style", {
      textContent: `
      :host { all: initial; }
      .wrap {
        position: fixed; top: 0; left: 0; right: 0; z-index: 2147483647;
        max-height: 80vh; overflow: auto; box-sizing: border-box;
        background: #7a1712; color: #fff; padding: 20px 24px 22px;
        font: 20px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        box-shadow: 0 6px 24px rgba(0,0,0,.5); border-bottom: 6px solid #ffd54a;
      }
      .inner { max-width: 900px; margin: 0 auto; }
      h1 { font-size: 28px; line-height: 1.25; margin: 0 0 8px; font-weight: 700; }
      p { margin: 8px 0; }
      ul { margin: 8px 0 8px 0; padding-left: 26px; }
      li { margin: 4px 0; }
      .do { background: rgba(0,0,0,.25); border-radius: 10px; padding: 10px 16px; margin: 12px 0; }
      .family { font-weight: 700; color: #ffe58a; }
      .buttons { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px; }
      button {
        font: inherit; font-weight: 700; padding: 12px 20px; border-radius: 10px;
        border: 3px solid #fff; cursor: pointer; min-height: 52px;
      }
      button:focus-visible { outline: 4px solid #ffd54a; outline-offset: 2px; }
      .primary { background: #fff; color: #7a1712; }
      .secondary { background: transparent; color: #fff; }
      .quiet { background: transparent; color: #fff; border-color: transparent; text-decoration: underline; font-weight: 400; }
    `
    });
    const reasons = el(
      "ul",
      {},
      scan.findings.slice(0, 3).map((f) => el("li", { textContent: f.reason }))
    );
    const advice = el("div", { className: "do" }, [
      el("p", {
        textContent: "Please do not call any phone number on this page, do not type a password or card number, and do not download anything."
      }),
      el("p", { textContent: "You are safe. Nothing bad happens if you simply close this page." })
    ]);
    if (family.familyName || family.familyPhone) {
      const who = family.familyName || "your family";
      const phone = family.familyPhone ? ` at ${family.familyPhone}` : "";
      advice.append(
        el("p", {
          className: "family",
          textContent: `Not sure? Call ${who}${phone} before you do anything.`
        })
      );
    }
    const closeBtn = el("button", { className: "primary", textContent: "Close this page" });
    closeBtn.addEventListener("click", () => chrome.runtime.sendMessage({ type: "closeTab" }));
    const askBtn = el("button", { className: "secondary", textContent: "Ask Grandson about it" });
    askBtn.addEventListener("click", () => chrome.runtime.sendMessage({ type: "openPanel" }).catch(() => {
    }));
    const hideBtn = el("button", { className: "quiet", textContent: "Hide this warning" });
    hideBtn.addEventListener("click", () => {
      dismissed = true;
      removeBanner();
    });
    root.append(
      style,
      el("div", { className: "wrap", role: "alertdialog", ariaLabel: "Scam warning from Grandson" }, [
        el("div", { className: "inner" }, [
          el("h1", { textContent: "Careful. This page looks like a scam." }),
          el("p", { textContent: "Grandson noticed these warning signs:" }),
          reasons,
          advice,
          el("div", { className: "buttons" }, [closeBtn, askBtn, hideBtn])
        ])
      ])
    );
    document.documentElement.append(host);
  }
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type !== "getPage") return;
    const text = pageText();
    sendResponse({
      url: location.href,
      title: document.title,
      text: text.slice(0, SHARE_TEXT_LIMIT),
      truncated: text.length > SHARE_TEXT_LIMIT,
      fields: pageFields(),
      scan: lastScan
    });
  });
  var timer = null;
  var lastRun = 0;
  function scheduleScan() {
    if (timer) return;
    const wait = Math.max(300, RESCAN_GAP_MS - (Date.now() - lastRun));
    timer = setTimeout(() => {
      timer = null;
      lastRun = Date.now();
      try {
        runScan();
      } catch {
      }
    }, wait);
  }
  if (window.top === window) {
    runScan();
    lastRun = Date.now();
    new MutationObserver((records) => {
      if (records.every((r) => r.target === document.documentElement && bannerHost)) return;
      scheduleScan();
    }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  }
})();
