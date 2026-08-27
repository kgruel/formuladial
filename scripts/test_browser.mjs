#!/usr/bin/env node
/** End-to-end confidence-flow checks against the generated static page. */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const chromium = [process.env.CHROMIUM, "/opt/homebrew/bin/chromium",
  "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]
  .find(candidate => candidate && existsSync(candidate));
if (!chromium) throw new Error("Set CHROMIUM to a Chromium/Chrome executable");
const profile = mkdtempSync(join(tmpdir(), "brezza-browser-test-"));
const port = 9300 + (process.pid % 500);
const child = spawn(chromium, [
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--no-default-browser-check",
  "--remote-allow-origins=*",
  "--window-size=1280,1000",
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`,
  pathToFileURL(join(root, "site/index.html")).href,
], { stdio: "ignore" });

const pause = ms => new Promise(resolvePromise => setTimeout(resolvePromise, ms));

async function targets() {
  for (let tries = 0; tries < 80; tries += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json`);
      if (response.ok) return await response.json();
    } catch {}
    await pause(50);
  }
  throw new Error("Chromium DevTools endpoint did not start");
}

let sequence = 0;
const pending = new Map();

async function main() {
  const pages = await targets();
  const page = pages.find(target => target.type === "page");
  assert(page, "Chromium did not open the generated page");

  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolvePromise, reject) => {
    socket.addEventListener("open", resolvePromise, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  socket.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve: done, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else done(message.result);
  });

  const send = (method, params = {}) => new Promise((resolvePromise, reject) => {
    const id = ++sequence;
    pending.set(id, { resolve: resolvePromise, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async expression => {
    const response = await send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (response.exceptionDetails) {
      throw new Error(response.exceptionDetails.exception?.description || "Browser evaluation failed");
    }
    return response.result.value;
  };
  const settle = () => evaluate("new Promise(resolve => setTimeout(resolve, 160))");
  const setValue = async (id, value, event = "change") => {
    await evaluate(`(() => { const node = document.getElementById(${JSON.stringify(id)}); ` +
      `node.value = ${JSON.stringify(value)}; node.dispatchEvent(new Event(${JSON.stringify(event)}, {bubbles:true})); })()`);
    await settle();
  };

  for (let tries = 0; tries < 40; tries += 1) {
    if (await evaluate("document.readyState === 'complete' && typeof run === 'function'")) break;
    await pause(50);
  }

  await setValue("q", "5099864016222", "input");
  await evaluate("q.focus()");
  assert.equal(await evaluate("getComputedStyle(q).outlineStyle"), "none",
    "The formula input must not draw a second focus ring inside its control");
  assert.notEqual(await evaluate("getComputedStyle(q.closest('.field')).boxShadow"), "none",
    "The formula control shell must carry the focus highlight");
  assert.match(await evaluate("empty.textContent"), /Start by choosing your machine/);
  assert.equal(await evaluate("document.getElementById('machine-step').classList.contains('needs')"), true);
  assert.equal(await evaluate("out.querySelectorAll('.dialsvg').length"), 0);

  await setValue("machine", "mini");
  assert.equal(await evaluate("lotrow.hidden"), true, "Mini must never expose lot-11 input");
  assert.equal(await evaluate("getComputedStyle(lotrow).display"), "none",
    "Mini lot input must be visually absent, not only marked hidden");
  assert.equal(await evaluate("document.getElementById('market-step').classList.contains('needs')"), true);
  assert.match(await evaluate("count.textContent"), /choose where the formula was sold/);
  assert.equal(await evaluate("out.querySelectorAll('.dialsvg').length"), 0,
    "Anywhere must never reveal an actionable dial");

  await setValue("terr", "Bahrain");
  await evaluate("terr.focus()");
  assert.equal(await evaluate("getComputedStyle(terr).outlineStyle"), "none",
    "The market input must not draw a second focus ring inside its control");
  assert.notEqual(await evaluate("getComputedStyle(terr.closest('.terr')).boxShadow"), "none",
    "The market control shell must carry the focus highlight");
  assert.match(await evaluate("count.textContent"), /Exact formula match/);
  assert.equal(await evaluate("out.querySelector('.dialsvg text').textContent"), "4");
  assert.equal(await evaluate("out.querySelector('.rec.result') !== null"), true);
  assert.equal(await evaluate("out.querySelector('.rec.result .dialsvg').getBoundingClientRect().width >= 96"), true);
  assert.match(await evaluate("out.querySelector('.observed').textContent"), /Last checked against Baby Brezza’s data/);
  assert.equal(await evaluate("document.getElementById('terr').getAttribute('list')"), "territories");
  assert.equal(await evaluate("document.getElementById('territories').options.length"), 78);
  assert.equal(await evaluate("document.querySelectorAll('[data-preview]').length > 0"), true);
  await evaluate("out.querySelector('[data-preview]').click()");
  await settle();
  assert.equal(await evaluate("document.getElementById('imagebox').open"), true);
  assert.equal(await evaluate("document.getElementById('imageboximg').naturalWidth > 128"), true,
    "The enlarged product image must use preview-quality local artwork");
  await evaluate("document.getElementById('imagebox').close()");
  if (process.env.SCREENSHOT) {
    const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
    writeFileSync(process.env.SCREENSHOT, Buffer.from(shot.data, "base64"));
  }
  if (process.env.MOBILE_SCREENSHOT) {
    await send("Emulation.setDeviceMetricsOverride", {
      width: 390, height: 844, deviceScaleFactor: 1, mobile: true,
    });
    await settle();
    assert.equal(await evaluate("getComputedStyle(document.querySelector('.setupgrid')).gridTemplateColumns.split(' ').length"), 1,
      "The lookup steps must collapse to one column on a phone");
    const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
    writeFileSync(process.env.MOBILE_SCREENSHOT, Buffer.from(shot.data, "base64"));
    await send("Emulation.clearDeviceMetricsOverride");
  }

  await setValue("q", "9347832001272", "input");
  await setValue("terr", "Australia/New Zealand");
  assert.match(await evaluate("count.textContent"), /2 possible matches/);
  assert.equal(await evaluate("out.querySelectorAll('[data-choice]').length"), 2);
  assert.equal(await evaluate("out.querySelectorAll('.dialsvg').length"), 0,
    "An ambiguous barcode must not reveal either setting");
  await evaluate("out.querySelector('[data-choice]').click()");
  assert.equal(await evaluate("out.querySelectorAll('.dialsvg').length"), 1,
    "Choosing the exact formula should reveal one setting");

  await setValue("q", "5900852071447", "input");
  await setValue("terr", "Albania");
  assert.match(await evaluate("out.textContent"), /publishes no usable setting/);
  assert.equal(await evaluate("out.querySelector('.dialsvg text').textContent"), "×",
    "Known-unavailable results may show a stop symbol, never a dial number");

  await setValue("q", "681131350204", "input");
  await setValue("terr", "Canada");
  assert.match(await evaluate("empty.textContent"), /No formula with that barcode/,
    "A US-only UPC must not bleed into its merged Canadian setting row");

  assert.equal(await evaluate("localStorage.getItem('brezza.q')"), null,
    "Formula searches must not persist across browser sessions");
  assert.equal(await evaluate("sessionStorage.getItem('brezza.q')"), "681131350204");
  assert.equal(await evaluate("document.querySelector('option[value=legacy]')"), null,
    "The historical machine must not appear in the primary app flow");
  assert.deepEqual(await evaluate("performance.getEntriesByType('resource').map(e => e.name).filter(url => /^https?:/.test(url))"), [],
    "The static app must not contact third parties during lookup");
  await evaluate("document.fonts.ready.then(() => true)");
  assert.equal(await evaluate("document.fonts.check('16px \\\"Source Sans 3\\\"') && document.fonts.check('16px \\\"Zilla Slab\\\"') && document.fonts.check('11px \\\"IBM Plex Mono\\\"')"), true,
    "The original typography must be available from the local app");

  await evaluate("localStorage.setItem('brezza.q', 'old persistent search')");
  await send("Page.reload", { ignoreCache: true });
  for (let tries = 0; tries < 40; tries += 1) {
    try {
      if (await evaluate("document.readyState === 'complete' && typeof run === 'function'")) break;
    } catch {}
    await pause(50);
  }
  assert.equal(await evaluate("localStorage.getItem('brezza.q')"), null,
    "An upgrade must clear formula searches persisted by older builds");

  socket.close();
  console.log("browser confidence flow: ok");
}

try {
  await main();
} finally {
  child.kill("SIGTERM");
  for (let tries = 0; tries < 20 && child.exitCode === null; tries += 1) await pause(50);
  if (child.exitCode === null) {
    child.kill("SIGKILL");
    await pause(100);
  }
  rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 50 });
}
