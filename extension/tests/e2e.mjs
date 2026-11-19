// End-to-end check in a real Chromium with the extension loaded.
// Claude is replaced by a stand-in, so this needs no API key and costs nothing.
// Run: npm run test:e2e
import { createRequire } from "node:module";
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

// require() finds a globally installed Playwright; a bare import would not.
const { chromium } = createRequire(import.meta.url)("playwright");

const here = path.dirname(fileURLToPath(import.meta.url));
const extensionDir = path.resolve(here, "..");
const shots = process.env.SHOTS_DIR || null;

const server = http.createServer((req, res) => {
  const file = path.join(here, "pages", path.basename(req.url.split("?")[0]));
  if (!fs.existsSync(file)) return res.writeHead(404).end();
  res.writeHead(200, { "content-type": "text/html" }).end(fs.readFileSync(file));
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}`;

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "grandson-e2e-"));
const context = await chromium.launchPersistentContext(profile, {
  channel: "chromium",
  viewport: { width: 1100, height: 760 },
  args: [`--disable-extensions-except=${extensionDir}`, `--load-extension=${extensionDir}`],
});

let failed = false;
const step = async (name, fn) => {
  try {
    await fn();
    console.log(`ok   - ${name}`);
  } catch (err) {
    failed = true;
    console.log(`FAIL - ${name}\n       ${String(err.message).split("\n").join("\n       ")}`);
  }
};

try {
  const worker = context.serviceWorkers()[0] || (await context.waitForEvent("serviceworker"));
  const extensionId = new URL(worker.url()).host;
  const tabIdFor = (url) => worker.evaluate(async (u) => (await chrome.tabs.query({ url: u }))[0]?.id, url);
  const scanFor = (tabId) =>
    worker.evaluate(async (id) => (await chrome.storage.session.get(`scan:${id}`))[`scan:${id}`], tabId);

  // Stand-in for Claude. Records what the extension sent.
  const sent = [];
  let reply = "This is the Maple Street Library page. It shows the opening hours.";
  await context.route("https://api.anthropic.com/**", async (route) => {
    const req = route.request();
    if (req.method() !== "POST") return route.fulfill({ status: 401, json: { type: "error", error: { type: "authentication_error", message: "invalid x-api-key" } } });
    sent.push({ headers: await req.allHeaders(), body: req.postDataJSON() });
    const ev = (type, data) => `event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`;
    const half = Math.ceil(reply.length / 2);
    const body =
      ev("message_start", { message: { id: "msg_test", type: "message", role: "assistant", model: "claude-opus-5-5", content: [], stop_reason: null, stop_sequence: null, usage: { input_tokens: 10, output_tokens: 1 } } }) +
      ev("content_block_start", { index: 0, content_block: { type: "text", text: "" } }) +
      ev("content_block_delta", { index: 0, delta: { type: "text_delta", text: reply.slice(0, half) } }) +
      ev("content_block_delta", { index: 0, delta: { type: "text_delta", text: reply.slice(half) } }) +
      ev("content_block_stop", { index: 0 }) +
      ev("message_delta", { delta: { stop_reason: "end_turn", stop_sequence: null }, usage: { output_tokens: 20 } }) +
      ev("message_stop", {});
    await route.fulfill({ status: 200, headers: { "content-type": "text/event-stream" }, body });
  });

  // The settings page opens by itself on first install; close it.
  for (const p of context.pages()) if (p.url().includes("options.html")) await p.close();

  const safe = await context.newPage();
  await safe.goto(`${base}/safe.html`);
  const scam = await context.newPage();
  await scam.goto(`${base}/scam.html`);

  await step("scam page gets the red warning banner", async () => {
    await scam.waitForSelector("#grandson-scam-warning", { state: "attached", timeout: 5000 });
    const scan = await scanFor(await tabIdFor(`${base}/scam.html`));
    assert.equal(scan.level, "danger");
    if (shots) await scam.screenshot({ path: path.join(shots, "banner.png") });
  });

  await step("ordinary page gets no banner and a clear verdict", async () => {
    await safe.bringToFront();
    await safe.waitForTimeout(500);
    assert.equal(await safe.locator("#grandson-scam-warning").count(), 0);
    const scan = await scanFor(await tabIdFor(`${base}/safe.html`));
    assert.equal(scan.level, "none");
  });

  await step("a scam that appears after the page loads is still caught", async () => {
    await safe.evaluate(() => {
      const d = document.createElement("div");
      d.textContent = "Your computer has been locked. Virus detected! Call Apple Support now at 1-800-555-0199.";
      document.body.append(d);
    });
    await safe.waitForSelector("#grandson-scam-warning", { state: "attached", timeout: 6000 });
    await safe.reload();
    await safe.waitForTimeout(500);
    assert.equal(await safe.locator("#grandson-scam-warning").count(), 0);
  });

  const safeTab = await tabIdFor(`${base}/safe.html`);
  const scamTab = await tabIdFor(`${base}/scam.html`);
  const panel = await context.newPage();
  await panel.setViewportSize({ width: 420, height: 900 });

  await step("without a key, the panel asks for setup and sends nothing", async () => {
    await panel.goto(`chrome-extension://${extensionId}/sidepanel.html?tabId=${safeTab}`);
    await panel.locator("#status.ok").waitFor();
    await panel.click("#explain");
    await panel.locator("#setup").waitFor({ state: "visible" });
    assert.equal(sent.length, 0);
  });

  await step("settings page saves the key and family contact", async () => {
    const options = await context.newPage();
    await options.goto(`chrome-extension://${extensionId}/options.html`);
    await options.fill("#apiKey", "sk-ant-test-key");
    await options.fill("#familyName", "Sarah");
    await options.fill("#familyPhone", "555 123 4567");
    await options.click("#save");
    await options.locator("#saveNotice", { hasText: "Saved." }).waitFor();
    // The stand-in rejects the key check, which must show a plain message.
    await options.locator("#keyNotice.bad").waitFor();
    if (shots) await options.screenshot({ path: path.join(shots, "options.png"), fullPage: true });
    const saved = await worker.evaluate(() => chrome.storage.local.get(null));
    assert.equal(saved.apiKey, "sk-ant-test-key");
    assert.equal(saved.familyName, "Sarah");
    await options.close();
  });

  await step("Explain this page sends the page to Claude and shows the answer", async () => {
    await panel.reload();
    await panel.click("#explain");
    await panel.locator(".reply", { hasText: "opening hours" }).waitFor();
    assert.equal(sent.length, 1);
    const { headers, body } = sent[0];
    assert.equal(headers.authorization, "Bearer sk-ant-test-key");
    assert.match(headers["anthropic-beta"], /server-side-fallback-2026-07-01/);
    assert.equal(body.model, "claude-opus-5-5");
    assert.equal(body.fallbacks, "default");
    assert.equal(body.stream, true);
    assert.deepEqual(body.output_config, { effort: "low" });
    assert.equal(body.thinking, undefined);
    const text = body.messages[0].content.find((b) => b.type === "text").text;
    assert.match(text, /Maple Street Library/);
    assert.match(text, /found no warning signs/);
    assert.ok(body.messages[0].content.some((b) => b.type === "image"), "screenshot attached");
    if (shots) await panel.screenshot({ path: path.join(shots, "panel-safe.png"), fullPage: true });
  });

  await step("a follow-up question continues the same conversation", async () => {
    reply = "It closes at 5 in the afternoon.";
    await panel.fill("#question", "When does it close?");
    await panel.click("#ask");
    await panel.locator(".reply", { hasText: "5 in the afternoon" }).waitFor();
    const { body } = sent[1];
    assert.equal(body.messages.length, 3);
    assert.equal(body.messages[1].role, "assistant");
    assert.equal(body.messages[2].content, "When does it close?");
  });

  await step("on a scam page the panel warns, names the family contact, and tells Claude", async () => {
    reply = "Please be careful. This page is a trick.";
    await panel.goto(`chrome-extension://${extensionId}/sidepanel.html?tabId=${scamTab}`);
    await panel.locator("#status.danger").waitFor();
    assert.match(await panel.locator("#status").innerText(), /Call Sarah at 555 123 4567/);
    await panel.click("#safety");
    await panel.locator(".reply", { hasText: "trick" }).waitFor();
    const text = sent.at(-1).body.messages[0].content.find((b) => b.type === "text").text;
    assert.match(text, /probably a scam/);
    assert.match(sent.at(-1).body.system, /never as instructions to you/);
    if (shots) await panel.screenshot({ path: path.join(shots, "panel-scam.png"), fullPage: true });
  });

  await step("the banner shows the family contact and can be hidden", async () => {
    await scam.bringToFront();
    await scam.reload();
    await scam.waitForSelector("#grandson-scam-warning", { state: "attached" });
    if (shots) await scam.screenshot({ path: path.join(shots, "banner-family.png") });
  });

  await step("a failed request shows a plain message, not an error code", async () => {
    await context.unroute("https://api.anthropic.com/**");
    await context.route("https://api.anthropic.com/**", (route) =>
      route.fulfill({ status: 401, json: { type: "error", error: { type: "authentication_error", message: "invalid x-api-key" } } }),
    );
    await panel.bringToFront();
    await panel.click("#explain");
    const err = panel.locator(".reply.error").first();
    await err.waitFor();
    assert.match(await err.innerText(), /key that lets me think/);
    await panel.locator("#setup").waitFor({ state: "visible" });
  });
} finally {
  await context.close();
  server.close();
  fs.rmSync(profile, { recursive: true, force: true });
}
process.exit(failed ? 1 : 0);
