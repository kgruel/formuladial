#!/usr/bin/env node
/** Render site/og.png, the 1200x630 social-unfurl card.
 *
 * Run manually when the card design changes -- og.png is a committed asset,
 * not a build_page.py output, because the page build is deterministic and
 * local-files-only while this needs a Chromium. The card deliberately carries
 * no dataset counts: a number baked into a PNG goes stale on the first crawl
 * that moves it, and nothing would regenerate it.
 *
 *   CHROMIUM="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
 *     node scripts/render_og.mjs
 */
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const WIDTH = 1200, HEIGHT = 630;

// The card reuses the page's actual hero dial -- the unfurl should promise
// exactly what the page shows.
const page = readFileSync(join(root, "site/index.html"), "utf8");
const hero = page.match(/<svg class="heromark"[\s\S]*?<\/svg>/)?.[0];
if (!hero) throw new Error("no heromark svg found in site/index.html");

const font = file => pathToFileURL(join(root, "site/fonts", file)).href;
const html = `<!doctype html><meta charset="utf-8"><style>
@font-face{font-family:"Source Sans 3";font-weight:400 600;src:url("${font("source-sans-3-latin.woff2")}") format("woff2")}
@font-face{font-family:"Zilla Slab";font-weight:700;src:url("${font("zilla-slab-700-latin.woff2")}") format("woff2")}
@font-face{font-family:"IBM Plex Mono";font-weight:600;src:url("${font("ibm-plex-mono-600-latin.woff2")}") format("woff2")}
:root{
  --ground:#f2f0ec; --ink:#1c2329; --ink-2:#4c565e; --ink-3:#5e6870;
  --dial:#c9821a; --dial-ink:#5a3a08; --dial-soft:#f6e6cd; --needle:#5a3a08;
}
*{margin:0; box-sizing:border-box}
body{width:${WIDTH}px; height:${HEIGHT}px; background:var(--ground);
  font-family:"Source Sans 3",sans-serif; color:var(--ink); overflow:hidden;
  display:flex; align-items:center; gap:56px; padding:0 84px 0 64px}
.heromark{width:430px; height:430px; flex:none; filter:drop-shadow(0 10px 26px rgba(90,58,8,.16))}
/* the spokes' stroke-width suits the page's 100px render; at 430px they fuse
   into wedges, so thin them back to hairlines at this scale */
.heromark path{stroke-width:.5}
.kicker{font-family:"IBM Plex Mono",monospace; font-weight:600; font-size:26px;
  letter-spacing:.24em; text-transform:uppercase; color:var(--dial-ink)}
h1{font-family:"Zilla Slab",serif; font-weight:700; font-size:74px;
  line-height:1.06; letter-spacing:-.01em; margin:18px 0 22px}
.tagline{font-size:33px; line-height:1.42; color:var(--ink-2); max-width:15em}
.machines{margin-top:34px; font-family:"IBM Plex Mono",monospace; font-weight:600;
  font-size:18px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-3); white-space:nowrap}
</style>
${hero}
<div>
  <div class="kicker">Formula Dial</div>
  <h1>What setting does this formula need?</h1>
  <p class="tagline">Every powder setting Baby Brezza publishes &mdash;
  searchable privately, in your browser.</p>
  <div class="machines">Formula Pro Advanced &middot; Advanced WiFi &middot; Mini</div>
</div>`;

const scratch = mkdtempSync(join(tmpdir(), "brezza-og-"));
const cardPath = join(scratch, "card.html");
writeFileSync(cardPath, html);

const chromium = [process.env.CHROMIUM, "/opt/homebrew/bin/chromium",
  "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]
  .find(candidate => candidate && existsSync(candidate));
if (!chromium) throw new Error("Set CHROMIUM to a Chromium/Chrome executable");
const port = 9200 + (process.pid % 500);
const child = spawn(chromium, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--remote-allow-origins=*", `--window-size=${WIDTH},${HEIGHT}`,
  `--remote-debugging-port=${port}`, `--user-data-dir=${join(scratch, "profile")}`,
  pathToFileURL(cardPath).href,
], { stdio: "ignore" });

const pause = ms => new Promise(done => setTimeout(done, ms));
async function pageTarget() {
  for (let tries = 0; tries < 80; tries += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json`);
      if (response.ok) {
        const target = (await response.json()).find(t => t.type === "page");
        if (target) return target;
      }
    } catch {}
    await pause(50);
  }
  throw new Error("Chromium DevTools endpoint did not start");
}

let sequence = 0;
const pending = new Map();
async function main() {
  const target = await pageTarget();
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((done, reject) => {
    socket.addEventListener("open", done, { once: true });
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
  const send = (method, params = {}) => new Promise((done, reject) => {
    sequence += 1;
    pending.set(sequence, { resolve: done, reject });
    socket.send(JSON.stringify({ id: sequence, method, params }));
  });

  await send("Emulation.setDeviceMetricsOverride",
    { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
  await pause(400); // let the woff2 faces finish loading
  const shot = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(root, "site/og.png"), Buffer.from(shot.data, "base64"));
  console.log(`wrote site/og.png (${WIDTH}x${HEIGHT})`);
  socket.close();
}

main().finally(() => { child.kill(); rmSync(scratch, { recursive: true, force: true }); });
