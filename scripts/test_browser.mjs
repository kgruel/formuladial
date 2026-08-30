#!/usr/bin/env node
/** End-to-end confidence-flow checks against the generated static page. */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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
// A Linux CI runner has no user namespaces to sandbox into, so Chrome exits
// before it opens the DevTools port -- and this harness spawns it with stdio
// ignored, so the only symptom is the endpoint never arriving. Kept off local
// runs, where the sandbox works and should stay on.
const ciFlags = process.env.CI ? ["--no-sandbox", "--disable-dev-shm-usage"] : [];
const child = spawn(chromium, [
  "--headless=new",
  "--disable-gpu",
  ...ciFlags,
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
  // Selection happens the way an owner does it: a click on the visible
  // machine button, not a synthetic value on some hidden control.
  const chooseMachine = async value => {
    await evaluate(`document.querySelector('[data-machine=${JSON.stringify(value)}]').click()`);
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

  await chooseMachine("mini");
  assert.equal(await evaluate("lotrow.hidden"), true, "Mini must never expose lot-11 input");
  assert.equal(await evaluate("getComputedStyle(lotrow).display"), "none",
    "Mini lot input must be visually absent, not only marked hidden");
  assert.equal(await evaluate("document.getElementById('market-step').classList.contains('needs')"), true);
  assert.match(await evaluate("count.textContent"), /^1 possible match$/,
    "The count slot states the quantity and nothing else");
  assert.match(await evaluate("out.querySelector('.choicehead h2').textContent"),
    /choose where it was sold/,
    "The imperative the count used to duplicate must still be in the heading below it");
  assert.equal(await evaluate("out.querySelectorAll('.dialsvg').length"), 0,
    "Anywhere must never reveal an actionable dial");

  await setValue("terr", "Bahrain");
  await evaluate("terr.focus()");
  assert.equal(await evaluate("getComputedStyle(terr).outlineStyle"), "none",
    "The market input must not draw a second focus ring inside its control");
  assert.notEqual(await evaluate("getComputedStyle(terr.closest('.terr')).boxShadow"), "none",
    "The market control shell must carry the focus highlight");
  assert.match(await evaluate("count.textContent"), /^Exact formula match/);
  assert.equal(await evaluate("out.querySelector('.dialsvg text').textContent"), "4");
  assert.equal(await evaluate("out.querySelector('.rec.result') !== null"), true);
  assert.equal(await evaluate("out.querySelector('.rec.result .dialsvg').getBoundingClientRect().width >= 96"), true);
  assert.match(await evaluate("out.querySelector('.observed').textContent"), /Last checked against Baby Brezza’s data/);

  // A row Baby Brezza lists without a usable setting counts toward ambiguity
  // exactly like a real candidate. Today's snapshot carries four such rows and
  // none of them collides with a record, so the rule is unreachable through the
  // UI -- and an unreachable rule is one a later refactor deletes without
  // noticing. Arm it with a synthetic row instead of trusting a source match.
  await evaluate(`(() => {
    const bit = 1n << BigInt(D.T.indexOf("Bahrain"));
    U.push([0, "Synthetic Ambiguity Row", "1", bit.toString(16), "no_setting",
            ["5099864016222"], null]);
    UHAY.push(fold(D.B[0] + " Synthetic Ambiguity Row 1"));
    UMASK.push(bit);
    run();
  })()`);
  assert.equal(await evaluate("out.querySelectorAll('.dialsvg text').length && out.querySelector('.dialsvg text').textContent !== '×'"), false,
    "A same-named row with no published setting must block the exact-match dial");
  assert.equal(await evaluate("out.querySelector('.rec.result')"), null,
    "One hit plus one unresolved sibling is not an exact match");
  assert.match(await evaluate("out.textContent"), /publishes no usable setting/,
    "The unresolved sibling must be listed as context");
  await evaluate("(() => { U.pop(); UHAY.pop(); UMASK.pop(); run(); })()");
  assert.equal(await evaluate("out.querySelector('.dialsvg text').textContent"), "4",
    "Removing the synthetic sibling restores the resolved setting");
  assert.equal(await evaluate("document.getElementById('terr').getAttribute('role') === 'combobox' && document.getElementById('terr').getAttribute('aria-controls')"), "territories");
  assert.equal(await evaluate("document.querySelectorAll('#territories [role=option]').length"), 78);

  // The alias that started all this: a real owner typed "USA", nothing matched,
  // and the page quietly searched every market instead of saying so. Driven
  // through real events rather than asserted against the handler's source --
  // a keydown branch that is only ever grepped for is one a refactor can delete
  // while the test stays green.
  const pressTerr = key => evaluate(
    `terr.dispatchEvent(new KeyboardEvent("keydown", {key:${JSON.stringify(key)}, bubbles:true, cancelable:true}))`);
  await setValue("terr", "", "input");
  await evaluate(`terr.focus(); terr.value = "USA"; terr.dispatchEvent(new Event("input", {bubbles:true}))`);
  await settle();
  assert.equal(await evaluate("terr.getAttribute('aria-expanded')"), "true",
    "Typing a market opens the listbox");
  assert.match(await evaluate("document.querySelector('#territories [role=option]').textContent"),
    /USA.*United States of America/,
    "An alias hit names both what was typed and the market it resolves to");
  await pressTerr("ArrowDown");
  await settle();
  assert.notEqual(await evaluate("terr.getAttribute('aria-activedescendant')"), "",
    "ArrowDown moves the active option");
  await pressTerr("Enter");
  await settle();
  assert.equal(await evaluate("terr.value"), "United States of America",
    "Choosing an alias rewrites the field to the market actually being filtered by");
  assert.equal(await evaluate("market()"), "United States of America");
  assert.equal(await evaluate("terr.getAttribute('aria-expanded')"), "false",
    "Choosing closes the listbox");
  await pressTerr("ArrowDown");
  await settle();
  await pressTerr("Escape");
  await settle();
  assert.equal(await evaluate("terr.getAttribute('aria-expanded')"), "false",
    "Escape closes the listbox again");
  // browsing markets without typing is the affordance the datalist never had
  await evaluate("document.getElementById('terrbtn').click()");
  await settle();
  assert.equal(await evaluate("document.querySelectorAll('#territories [role=option]').length"), 78,
    "The toggle offers every market with nothing typed");
  await evaluate("document.getElementById('terrbtn').click()");
  await settle();
  await setValue("terr", "Bahrain");
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
  assert.match(await evaluate("count.textContent"), /^2 possible matches$/,
    "The count slot states the quantity and nothing else");
  assert.match(await evaluate("out.querySelector('.choicehead h2').textContent"),
    /which formula matches your container\?/,
    "The imperative the count used to duplicate must still be in the heading below it");
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

  // The lot placeholder is authored copy, not a lot number: text-transform must
  // normalise what the owner types without uppercasing -- and clipping -- it.
  await chooseMachine("advanced");
  assert.equal(await evaluate("lotrow.hidden"), false, "Advanced must expose the lot input");
  assert.equal(await evaluate("getComputedStyle(lot).textTransform"), "uppercase",
    "A typed lot number must still be normalised to uppercase");
  await evaluate("document.fonts.ready.then(() => true)");
  const overflowingPlaceholders = () => evaluate(`(() => {
    const canvas = document.createElement("canvas").getContext("2d");
    return [...document.querySelectorAll("input[placeholder]")]
      .filter(input => input.getClientRects().length)
      .map(input => {
        const style = getComputedStyle(input, "::placeholder");
        const text = style.textTransform === "uppercase"
          ? input.placeholder.toUpperCase() : input.placeholder;
        canvas.font = [style.fontStyle, style.fontWeight, style.fontSize, style.fontFamily].join(" ");
        return { id: input.id, text, width: canvas.measureText(text).width, room: input.clientWidth };
      })
      .filter(measured => measured.width > measured.room);
  })()`);
  // The viewport widths this page's copy is budgeted for. "Every placeholder
  // fits" is only ever true at some width, so the widths are named here rather
  // than being whatever the harness last set -- that is how this check read
  // green at 1280 while the search placeholder had been clipped on every phone.
  // 390 is the floor by decision: iPhone 12-16, Pixel, current Android. 375 and
  // below (iPhone SE 2/3, 8, 13 mini) are out of scope -- neither the search
  // copy (fails at 380) nor the lot copy (fails at 375) fits there. Adding a
  // width here is a copy-budget decision, not a test tweak: review it as one.
  const SUPPORTED_WIDTHS = [1280, 390];
  for (const width of SUPPORTED_WIDTHS) {
    await send("Emulation.setDeviceMetricsOverride",
      { width, height: 844, deviceScaleFactor: 1, mobile: width < 700 });
    await settle();
    await evaluate("document.fonts.ready.then(() => true)");
    assert.equal(await evaluate("lotrow.hidden"), false,
      `The ${width}px placeholder pass is vacuous unless the lot input is shown`);
    const clipped = await overflowingPlaceholders();
    assert.deepEqual(clipped, [], clipped.map(one =>
      `At ${width}px, #${one.id} placeholder ${JSON.stringify(one.text)} renders ` +
      `${one.width.toFixed(1)}px into ${one.room}px of control: clipped by ` +
      `${(one.width - one.room).toFixed(1)}px`).join("\n"));
  }
  // ---- the heading holds its line beside the mark ----
  // The header puts the mark beside the heading above 900px. Its predecessor
  // did the same at every width, which left the h1 only 56px of slack at 768
  // and wrapped it. The rule is that the heading holds one line wherever the
  // layout is wide enough to be a heading -- pinned by measurement, not by
  // class name, so a two-column header under any name has to satisfy it.
  const HEADING_WIDTHS = [1280, 1024, 900, 899, 820, 768];
  for (const width of HEADING_WIDTHS) {
    await send("Emulation.setDeviceMetricsOverride",
      { width, height: 900, deviceScaleFactor: 1, mobile: false });
    await settle();
    await evaluate("document.fonts.ready.then(() => true)");
    const lines = await evaluate(`(() => {
      const h = document.querySelector("h1");
      return Math.round(h.getBoundingClientRect().height
        / parseFloat(getComputedStyle(h).lineHeight));
    })()`);
    assert.equal(lines, 1,
      `The heading must hold one line at ${width}px; it wrapped onto ${lines}`);
    assert.equal(
      await evaluate(`getComputedStyle(document.querySelector(".hrow")).display`),
      width >= 900 ? "grid" : "block",
      `At ${width}px the header must ${width >= 900 ? "sit two-column" : "stack"}`);
  }
  await send("Emulation.clearDeviceMetricsOverride");
  await settle();

  await send("Emulation.clearDeviceMetricsOverride");
  await settle();

  // ---- the lot number as a conditional fourth gate ----
  // Everything else on this page refuses a number until the ambiguity
  // resolves. Where a record carries an alternate, an unentered lot is exactly
  // that kind of ambiguity, so it is walked here in all of its states: gated,
  // resolved both ways, and the three shapes it must never fire in.
  const dialNumbers = () =>
    evaluate("[...out.querySelectorAll('.dialsvg text')].map(t => t.textContent)");
  const stepClasses = id =>
    evaluate(`[...document.getElementById(${JSON.stringify(id)}).classList]`);

  await setValue("terr", "United States of America");
  await setValue("lot", "", "input");
  await setValue("q", "bobbie organic gentle", "input");
  assert.deepEqual(await dialNumbers(), ["?"],
    "A formula whose setting depends on the lot must show no dial number");
  assert.equal(await evaluate("out.querySelector('.rec.result.asking') !== null"), true);
  assert.match(await evaluate("out.querySelector('.asklot').textContent"),
    /depends on your machine’s lot number.*sticker underneath the machine and enter the lot number in step 1/s,
    "The reason must be visible copy, not a title tooltip that touch cannot open");
  assert.equal(await evaluate("out.querySelector('.asklot').getClientRects().length > 0"), true,
    "The prompt must be rendered, not merely present in the markup");
  // amber, not either of the two red stop faces: this state is answerable.
  // resolved through a probe so a token and a painted stroke are comparable
  const resolveToken = token => evaluate(`(() => { const probe = document.createElement("span"); ` +
    `probe.style.color = "var(${token})"; document.body.append(probe); ` +
    `const painted = getComputedStyle(probe).color; probe.remove(); return painted })()`);
  const askStroke = await evaluate("getComputedStyle(out.querySelector('.rec.result .dialsvg circle')).stroke");
  const stopStroke = await resolveToken("--stop");
  const dialStroke = await resolveToken("--dial");
  assert.notEqual(askStroke, stopStroke, "The lot-gated face must not borrow the stop red");
  assert.equal(askStroke, dialStroke, "The lot-gated face belongs to the --dial amber family");
  // the blocker moves to step 1; step 3 has resolved and keeps its tick.
  assert.deepEqual(await stepClasses("machine-step"), ["step", "needs"]);
  assert.deepEqual(await stepClasses("search-step"), ["step", "searchstep", "done"]);
  assert.equal(await evaluate("document.getElementById('machine-status').textContent"),
    "Lot number needed");
  assert.equal(await evaluate("lotstate.className"), "lotstate need");

  await setValue("lot", "1123ABC", "input");
  assert.deepEqual(await dialNumbers(), ["6"], "A lot-11 machine takes the alternate");
  assert.equal(await evaluate("out.querySelector('.rec.result.asking')"), null);
  await setValue("lot", "2200XYZ", "input");
  assert.deepEqual(await dialNumbers(), ["5"], "Any other lot takes the standard number");
  assert.equal(await evaluate("out.querySelector('.rec.result.asking')"), null);

  // a record with no alternate: the lot changes nothing, so it never gates.
  await setValue("lot", "", "input");
  await setValue("q", "A2 Milk Platinum", "input");
  assert.deepEqual(await dialNumbers(), ["4"],
    "A formula without an alternate must answer with a blank lot field");
  assert.deepEqual(await stepClasses("machine-step"), ["step", "done"]);

  // Mini never reads the lot, so it is never gated by one.
  await chooseMachine("mini");
  await setValue("terr", "United States of America");
  await setValue("q", "bobbie organic gentle", "input");
  assert.deepEqual(await dialNumbers(), ["5"],
    "Mini always answers with the standard setting, gate or no gate");
  assert.equal(await evaluate("out.querySelector('.std')"), null,
    "Mini must not be told about the lot-11 alternate it cannot use");

  // two of the 99 alternates are 0: the gate must be able to land in the
  // existing red no-dial-position face, not only on a number.
  await chooseMachine("advanced");
  await setValue("terr", "United States of America");
  await setValue("lot", "11ABCD", "input");
  await setValue("q", "enfagrow gentlease toddler", "input");
  assert.deepEqual(await dialNumbers(), ["0"]);
  assert.match(await evaluate("out.querySelector('.nope').textContent"), /No dial position/);
  assert.equal(await evaluate("getComputedStyle(out.querySelector('.rec.result .dialsvg circle')).stroke"),
    stopStroke, "A lot-11 alternate of 0 is a stop, and takes the stop red");
  await setValue("lot", "", "input");
  assert.deepEqual(await dialNumbers(), ["?"],
    "The same record with no lot is undecided, not a stop");

  // a row Baby Brezza publishes no setting for is a candidate, not a choice:
  // it forces the choice state and is listed below as context. The fold has to
  // separate it like any other candidate, or a lone hit beside a lone
  // unavailable sibling would have nothing left to narrow on.
  await setValue("terr", "Australia/New Zealand");
  await setValue("q", "neocate syneo", "input");
  assert.match(await evaluate("count.textContent"), /^2 possible matches$/);
  assert.equal(await evaluate("out.querySelectorAll('[data-fold]').length"), 2,
    "Both candidates are foldable, including the one with no published setting");
  assert.equal(await evaluate("out.querySelectorAll('.warning').length"), 1,
    "The row with no published setting is listed, and says so");
  assert.deepEqual(await dialNumbers(), ["×"],
    "A same-named row with no setting must not leave a number asserted as exact");
  await evaluate("[...out.querySelectorAll('[data-fold]')].find(b => b.textContent.includes('Nutricia')).click()");
  await settle();
  assert.deepEqual(await dialNumbers(), ["4", "×"],
    "Narrowing resolves the ambiguity and keeps the unavailable sibling as context");

  // step 3 is done when the search has resolved, never because it has text.
  await setValue("terr", "United States of America");
  await setValue("q", "xyzzy-nonsense", "input");
  assert.deepEqual(await stepClasses("search-step"), ["step", "searchstep", "needs"],
    "A search with no match has not resolved, so it cannot be ticked done");
  assert.match(await evaluate("empty.textContent"), /Nothing matching that/);

  // forced-colors drops box-shadow and border-color, so the shell ring above is
  // invisible there; only a real outline keeps keyboard focus visible.
  await send("Emulation.setEmulatedMedia", {
    features: [{ name: "forced-colors", value: "active" }],
  });
  await evaluate("q.focus()");
  await settle();
  assert.notEqual(await evaluate("getComputedStyle(q).outlineStyle"), "none",
    "Focus must stay visible as an outline under forced-colors");
  assert.notEqual(await evaluate("getComputedStyle(q).outlineWidth"), "0px",
    "The forced-colors focus outline must have width");
  await send("Emulation.setEmulatedMedia", { features: [] });

  // ---- opt-in persistence: pins and the remembered lot ----
  // The stored shapes are the invariant: a pin is identity + market, never a
  // setting; the lot lands in localStorage only while its box is ticked. The
  // segment ends with storage swept clean, so the census below starts from
  // the state its drives assume.
  await chooseMachine("advanced");
  await setValue("terr", "United States of America");
  await setValue("lot", "1123ABC", "input");
  await setValue("q", "bobbie organic gentle", "input");
  assert.notEqual(await evaluate("out.querySelector('[data-pinbtn]')"), null,
    "A resolved result offers the pin action");
  await evaluate("out.querySelector('[data-pinbtn]').click()");
  await settle();
  assert.equal(await evaluate("document.getElementById('pinrow').hidden"), false,
    "Pinning reveals the pinned-formula chips");
  const storedPins = JSON.parse(await evaluate("localStorage.getItem('brezza.pins')"));
  assert.equal(storedPins.length, 1);
  assert.deepEqual(Object.keys(storedPins[0]).sort(), ["b", "m", "s", "t"],
    "A pin stores identity and market only, never a setting");
  assert.match(await evaluate("out.querySelector('.pinbtn').textContent"), /Pinned/);

  // the lot may persist only after the owner opts in, and tracks the field
  assert.equal(await evaluate("localStorage.getItem('brezza.lot')"), null,
    "The lot must not persist before the owner opts in");
  await evaluate("(() => { const k = document.getElementById('lotkeep'); " +
    "k.checked = true; k.dispatchEvent(new Event('change', {bubbles:true})); })()");
  await settle();
  assert.equal(await evaluate("localStorage.getItem('brezza.lot')"), "1123ABC");

  // a fresh load of the same document: the pin and the kept lot come back,
  // and the chip replays the lookup through current data -- the lot-11
  // alternate, not a number the pin could have saved.
  await send("Page.navigate", { url: pathToFileURL(join(root, "site/index.html")).href });
  for (let tries = 0; tries < 40; tries += 1) {
    if (await evaluate("document.readyState === 'complete' && typeof run === 'function'")) break;
    await pause(50);
  }
  await settle();
  assert.equal(await evaluate("document.getElementById('lot').value"), "1123ABC",
    "An opted-in lot is restored on return");
  assert.equal(await evaluate("document.getElementById('lotkeep').checked"), true);
  assert.equal(await evaluate("document.getElementById('pinrow').hidden"), false,
    "Pinned chips are offered before any search on return");
  await evaluate("q.value = ''; q.dispatchEvent(new Event('input', {bubbles:true}))");
  await settle();
  await evaluate("document.querySelector('#pinchips [data-pin]').click()");
  await settle();
  assert.deepEqual(await dialNumbers(), ["6"],
    "A pin replays the lookup: the lot-11 alternate wins, not a saved number");

  // sweep: unpin from the card, untick the box -- storage returns to empty
  await evaluate("out.querySelector('[data-pinbtn]').click()");
  await settle();
  assert.equal(await evaluate("document.getElementById('pinrow').hidden"), true);
  assert.equal(await evaluate("localStorage.getItem('brezza.pins')"), "[]");
  await evaluate("(() => { const k = document.getElementById('lotkeep'); " +
    "k.checked = false; k.dispatchEvent(new Event('change', {bubbles:true})); })()");
  await settle();
  assert.equal(await evaluate("localStorage.getItem('brezza.lot')"), null,
    "Unticking sweeps the kept lot");

  // ---- adaptive fold: US market with query 'Similac' renders fold rows ----
  await chooseMachine("advanced");
  await setValue("terr", "United States of America");
  await setValue("lot", "");
  await setValue("q", "Similac", "input");
  // The invariant is that a fold level shows nothing actionable -- not that it
  // shows no dial face at all. A row with no published setting renders the red
  // stop face, and that face is the opposite of an instruction: it is already
  // how the page says "do not use this".
  assert.equal(await evaluate("out.querySelectorAll('[data-fold] .dialsvg, [data-fold] .thumb').length"), 0,
    "A fold row carries no dial face and no product image of its own");
  assert.deepEqual((await dialNumbers()).filter(text => /^[0-9]+$/.test(text)), [],
    "A fold level must never show an actionable dial number");
  const similacTypeRows = await evaluate("out.querySelectorAll('[data-fold]').length");
  // Every Similac candidate shares the brand, so the brand column is skipped and
  // the ladder lands on type. Note what this case does NOT show: the US Similac
  // catalogue is 31 types over 32 candidates, so the fold barely reduces it. The
  // reduction that matters for this lookup is the market gate (179 candidates
  // across all markets down to 32), not the fold. The fold earns its keep on
  // deep catalogues -- see the Nestle NAN case below -- and on the browse path.
  // Asserted as a property of the data rather than a literal, so a re-crawl that
  // adds a Similac product does not turn this red.
  const distinctSimilacTypes = await evaluate(`(() => {
    const bit = 1n << BigInt(D.T.indexOf("United States of America"));
    const seen = new Set();
    D.R.forEach((r, i) => { if ((MASK[i] & bit) && HAY[i].includes("similac")) seen.add(r[1]) });
    U.forEach((r, i) => { if ((UMASK[i] & bit) && UHAY[i].includes("similac")) seen.add(r[1]) });
    return seen.size;
  })()`);
  assert.equal(similacTypeRows, distinctSimilacTypes,
    "Similac in the US folds to exactly one row per distinct product type");
  assert.equal(await evaluate("out.querySelectorAll('.choice').length"), 0,
    "Similac in US must not render flat choice cards");

  // ---- adaptive fold: exact-field filter prevents substring bleed ----
  await setValue("terr", "Austria");
  await setValue("q", "", "input");
  // A silently-skipped click makes this whole scenario pass without testing
  // anything, so the helper throws rather than shrugging when the row is absent.
  const clickFold = async (key, value) => {
    const clicked = await evaluate(`(() => {
      const btn = [...document.querySelectorAll('[data-fold=${JSON.stringify(key)}]')]
        .find(b => b.dataset.val === ${JSON.stringify(value)});
      if (!btn) return false;
      btn.click();
      return true;
    })()`);
    assert.equal(clicked, true, `fold row ${key}=${value} was not on the page to click`);
    await settle();
  };
  // Nestlé NAN is not one of the popular twelve, so the brand level is capped
  // until the expander is taken -- the browse path an owner actually walks.
  await evaluate("document.querySelector('[data-expand]').click()");
  await settle();
  await clickFold("b", "Nestlé NAN");
  await clickFold("t", "Optipro");
  // Under Optipro type in Austria, there are exactly 5 stages (1, 2, 3, 4, 5), not 10 from Optipro Plus HMO
  const optiproStages = await evaluate("out.querySelectorAll('[data-fold=\"s\"]').length");
  assert.equal(optiproStages, 5,
    "Picking type Optipro under Nestlé NAN in Austria must show exactly 5 stages, not 10 from Optipro Plus HMO");
  // Each crumb is two buttons -- the label, which steps back to that level, and
  // its remove x -- so count crumbs, not elements carrying the attribute.
  assert.equal(await evaluate("document.querySelectorAll('#crumbs .pin').length"), 2,
    "Crumbs must show pinned brand and type");

  // ---- adaptive fold: no fold level ever renders exactly one row ----
  for (const terr of ["United States of America", "Austria", "Canada", "Germany"]) {
    await setValue("terr", terr);
    await setValue("q", "", "input");
    const count = await evaluate("out.querySelectorAll('[data-fold]').length");
    if (count > 0) {
      assert.notEqual(count, 1, `Brand fold level in ${terr} must not have exactly 1 row`);
    }
  }
  await setValue("terr", "United States of America");
  await setValue("q", "Enfamil", "input");
  const enfamilTypes = await evaluate("out.querySelectorAll('[data-fold]').length");
  assert.notEqual(enfamilTypes, 1, "Enfamil type fold level must not have exactly 1 row");

  // ---- adaptive fold: empty query with market selected renders the brand list ----
  await setValue("terr", "United States of America");
  // Clear any filter crumbs first
  await evaluate("(() => { const c = document.querySelector('[data-crumb=\"b\"]'); if (c) c.click(); })()");
  await settle();
  await setValue("q", "", "input");
  const brandRows = await evaluate("out.querySelectorAll('[data-fold=\"b\"]').length");
  assert.equal(brandRows > 1, true,
    "An empty query with a market selected must render the brand list");
  const firstBrand = await evaluate("out.querySelector('[data-fold=\"b\"] .name').textContent");
  assert.equal(firstBrand, "Enfamil", "Brand list must sort QUICK brands first in QUICK order");
  const totalUSBrands = await evaluate("new Set(D.R.filter(r => (BigInt('0x'+r[4]) & (1n << BigInt(D.T.indexOf('United States of America')))) !== 0n).map(r => D.B[r[0]])).size");
  if (totalUSBrands > 12) {
    assert.equal(brandRows, 12, "Brand list must show at most 12 rows initially");
    assert.notEqual(await evaluate("out.querySelector('[data-expand=\"brands\"]')"), null,
      "Brand list with >12 brands must offer an expander");
    await evaluate("out.querySelector('[data-expand=\"brands\"]').click()");
    await settle();
    assert.equal(await evaluate("out.querySelectorAll('[data-fold=\"b\"]').length"), totalUSBrands,
      "Clicking expander must show all brands");
  }

  // Clear state for subsequent tests
  await evaluate("(() => { const c = document.querySelector('[data-crumb=\"b\"]'); if (c) c.click(); })()");
  await setValue("q", "", "input");
  await setValue("terr", "");
  await settle();

  // ---- reset classes: field clear buttons, start over, forget device ----

  // 1. Start over is absent on a fresh page and present once a search has been typed
  await evaluate("localStorage.clear(); sessionStorage.clear()");
  await send("Page.reload", { ignoreCache: true });
  for (let tries = 0; tries < 40; tries += 1) {
    try {
      if (await evaluate("document.readyState === 'complete' && typeof run === 'function'")) break;
    } catch {}
    await pause(50);
  }
  await settle();

  assert.equal(await evaluate("document.getElementById('reset').hidden"), true,
    "Start over is absent on a fresh page");
  assert.equal(await evaluate("document.getElementById('q-clear').hidden"), true,
    "Search clear button is absent on a fresh page");
  assert.equal(await evaluate("document.getElementById('terr-clear').hidden"), true,
    "Market clear button is absent on a fresh page");
  assert.equal(await evaluate("document.getElementById('lot-clear').hidden"), true,
    "Lot clear button is absent on a fresh page");

  await chooseMachine("advanced");
  await setValue("terr", "United States of America");
  assert.equal(await evaluate("document.getElementById('reset').hidden"), true,
    "Start over is absent when machine and market are set but no search or filter exists");

  await setValue("q", "Similac", "input");
  assert.equal(await evaluate("document.getElementById('reset').hidden"), false,
    "Start over is present once a search has been typed");

  // 2. Start over clears the search box and the crumbs, and leaves machine, market, lot and pins intact
  // Set up device facts: machine, market, lot (opted in), pinned formula
  await setValue("lot", "1123ABC", "input");
  await evaluate("(() => { const k = document.getElementById('lotkeep'); " +
    "k.checked = true; k.dispatchEvent(new Event('change', {bubbles:true})); })()");
  await settle();
  // Pin a formula
  await setValue("q", "bobbie organic gentle", "input");
  assert.notEqual(await evaluate("out.querySelector('[data-pinbtn]')"), null);
  await evaluate("out.querySelector('[data-pinbtn]').click()");
  await settle();
  assert.equal(await evaluate("pins.length"), 1, "Formula is pinned");

  // Browsing is lookup state too: a market chosen and a brand drilled into, with
  // nothing typed at all. Start over has to be reachable from there, so the
  // control's visibility rule must read fold state and not only the search box.
  await setValue("q", "", "input");
  await settle();
  await evaluate("out.querySelector('[data-fold]').click()");
  await settle();
  assert.equal(await evaluate("document.querySelectorAll('#crumbs .pin').length"), 1,
    "browsing into a fold level pins a crumb");
  assert.equal(await evaluate("document.getElementById('reset').hidden"), false,
    "Start over is reachable from the browse path, where nothing has been typed");

  // Now create lookup state: search query + fold crumbs
  await setValue("q", "Similac", "input");
  assert.equal(await evaluate("document.getElementById('reset').hidden"), false);
  // The crumb assertions after Start over are only meaningful if a crumb exists
  // when it runs. Without this the filter is already empty and they pass on an
  // empty set -- which is exactly why deleting clearFold() from the handler left
  // this suite green.
  await evaluate("out.querySelector('[data-fold]').click()");
  await settle();
  assert.equal(await evaluate("document.querySelectorAll('#crumbs .pin').length"), 1,
    "precondition: a fold crumb is pinned before Start over runs");

  // Click "Start over"
  await evaluate("document.getElementById('reset').click()");
  await settle();

  // Assert lookup state is cleared:
  assert.equal(await evaluate("q.value"), "", "Start over clears the search box");
  assert.equal(await evaluate("sessionStorage.getItem('brezza.q') || ''"), "",
    "Start over clears brezza.q in sessionStorage");
  assert.equal(await evaluate("document.querySelectorAll('#crumbs .pin').length"), 0,
    "Start over clears fold crumbs");
  assert.deepEqual(await evaluate("filter"), {b:null, t:null, s:null},
    "Start over resets fold filter state");
  assert.equal(await evaluate("document.getElementById('reset').hidden"), true,
    "Start over is hidden after clearing lookup state");
  assert.equal(await evaluate("document.activeElement.id"), "q",
    "Start over returns focus to the search box");

  // Assert each of the four device facts explicitly:
  // (a) machine
  assert.equal(await evaluate("machine"), "advanced", "Start over leaves machine intact");
  assert.equal(await evaluate("localStorage.getItem('brezza.machine')"), "advanced",
    "Start over leaves brezza.machine in localStorage intact");
  // (b) market
  assert.equal(await evaluate("terr.value"), "United States of America",
    "Start over leaves market input intact");
  assert.equal(await evaluate("market()"), "United States of America",
    "Start over leaves market() intact");
  assert.equal(await evaluate("localStorage.getItem('brezza.terr')"), "United States of America",
    "Start over leaves brezza.terr in localStorage intact");
  // (c) lot
  assert.equal(await evaluate("lot.value"), "1123ABC", "Start over leaves lot input intact");
  assert.equal(await evaluate("lotkeep.checked"), true, "Start over leaves lotkeep checked");
  assert.equal(await evaluate("localStorage.getItem('brezza.lot')"), "1123ABC",
    "Start over leaves brezza.lot in localStorage intact");
  assert.equal(await evaluate("sessionStorage.getItem('brezza.lot')"), "1123ABC",
    "Start over leaves brezza.lot in sessionStorage intact");
  // (d) pins
  assert.equal(await evaluate("pins.length"), 1, "Start over leaves pins intact");
  assert.equal(await evaluate("document.getElementById('pinrow').hidden"), false,
    "Start over leaves pinned row visible");
  assert.notEqual(await evaluate("localStorage.getItem('brezza.pins')"), "[]",
    "Start over leaves brezza.pins in localStorage intact");

  // 3. Each field's clear button empties only its own field
  // Set all three fields
  await setValue("q", "Similac", "input");
  await setValue("terr", "United States of America");
  await setValue("lot", "1123ABC", "input");
  assert.equal(await evaluate("document.getElementById('q-clear').hidden"), false);
  assert.equal(await evaluate("document.getElementById('terr-clear').hidden"), false);
  assert.equal(await evaluate("document.getElementById('lot-clear').hidden"), false);

  // (a) Lot clear button empties only lot
  await evaluate("document.getElementById('lot-clear').click()");
  await settle();
  assert.equal(await evaluate("lot.value"), "", "Lot clear button empties lot field");
  assert.equal(await evaluate("document.getElementById('lot-clear').hidden"), true);
  assert.equal(await evaluate("q.value"), "Similac", "Lot clear button leaves search intact");
  assert.equal(await evaluate("terr.value"), "United States of America",
    "Lot clear button leaves market intact");
  assert.equal(await evaluate("document.activeElement.id"), "lot",
    "Lot clear button returns focus to lot field");

  // (b) Search clear button empties only search
  await setValue("lot", "1123ABC", "input");
  await evaluate("document.getElementById('q-clear').click()");
  await settle();
  assert.equal(await evaluate("q.value"), "", "Search clear button empties search field");
  assert.equal(await evaluate("document.getElementById('q-clear').hidden"), true);
  assert.equal(await evaluate("terr.value"), "United States of America",
    "Search clear button leaves market intact");
  assert.equal(await evaluate("lot.value"), "1123ABC", "Search clear button leaves lot intact");
  assert.equal(await evaluate("document.activeElement.id"), "q",
    "Search clear button returns focus to search field");

  // (c) Market clear button empties only market
  await setValue("q", "Similac", "input");
  await evaluate("document.getElementById('terr-clear').click()");
  await settle();
  assert.equal(await evaluate("terr.value"), "", "Market clear button empties market field");
  assert.equal(await evaluate("document.getElementById('terr-clear').hidden"), true);
  assert.equal(await evaluate("q.value"), "Similac", "Market clear button leaves search intact");
  assert.equal(await evaluate("lot.value"), "1123ABC", "Market clear button leaves lot intact");
  assert.equal(await evaluate("document.activeElement.id"), "terr",
    "Market clear button returns focus to market field");

  // 4. Clearing the market also drops the fold crumbs
  await setValue("q", "", "input");
  await setValue("terr", "Austria");
  await evaluate("document.querySelector('[data-expand]').click()");
  await settle();
  await clickFold("b", "Nestlé NAN");
  await clickFold("t", "Optipro");
  assert.equal(await evaluate("document.querySelectorAll('#crumbs .pin').length"), 2,
    "Crumbs present before clearing market");
  await evaluate("document.getElementById('terr-clear').click()");
  await settle();
  assert.equal(await evaluate("terr.value"), "", "Market is cleared");
  assert.equal(await evaluate("document.querySelectorAll('#crumbs .pin').length"), 0,
    "Clearing the market also drops the fold crumbs");
  assert.deepEqual(await evaluate("filter"), {b:null, t:null, s:null},
    "Clearing market resets fold filter");

  // 5. Forget this device empties every brezza.* key from BOTH storages and returns the page to the 'Start by choosing your machine' state
  // Set up all storages with state
  await chooseMachine("advanced");
  await setValue("terr", "United States of America");
  await setValue("lot", "1123ABC", "input");
  await setValue("q", "Similac", "input");
  await evaluate("(() => { " +
    "localStorage.setItem('brezza.theme', 'dark'); " +
    "localStorage.setItem('brezza.custom_probe', '123'); " +
    "sessionStorage.setItem('brezza.custom_probe', '456'); " +
    "})()");
  assert.equal(await evaluate("machine"), "advanced");
  assert.equal(await evaluate("pins.length"), 1);

  // Click "Forget this device"
  await evaluate("document.getElementById('forget').click()");
  await settle();

  // Check all brezza.* keys are gone from localStorage and sessionStorage
  const remainingLocalStorageKeys = await evaluate("Object.keys(localStorage).filter(k => k.startsWith('brezza.'))");
  assert.deepEqual(remainingLocalStorageKeys, [],
    "Forget this device empties every brezza.* key from localStorage");
  const remainingSessionStorageKeys = await evaluate("Object.keys(sessionStorage).filter(k => k.startsWith('brezza.'))");
  assert.deepEqual(remainingSessionStorageKeys, [],
    "Forget this device empties every brezza.* key from sessionStorage");

  // Check page returned to initial "Start by choosing your machine" state
  assert.equal(await evaluate("machine"), "", "Forget this device clears machine state");
  assert.equal(await evaluate("document.querySelectorAll('[data-machine][aria-pressed=\"true\"]').length"), 0,
    "No machine choice is pressed");
  assert.equal(await evaluate("lotrow.hidden"), true, "Lot row is hidden");
  assert.equal(await evaluate("terr.value"), "", "Market input is empty");
  assert.equal(await evaluate("q.value"), "", "Search input is empty");
  assert.equal(await evaluate("lot.value"), "", "Lot input is empty");
  assert.equal(await evaluate("lotkeep.checked"), false, "Lot remember is unchecked");
  assert.equal(await evaluate("pins.length"), 0, "Pins are cleared");
  assert.equal(await evaluate("document.getElementById('pinrow').hidden"), true, "Pins row is hidden");
  assert.match(await evaluate("empty.textContent"), /Start by choosing your machine/,
    "Page shows 'Start by choosing your machine'");
  assert.equal(await evaluate("document.getElementById('machine-step').classList.contains('needs')"), true,
    "Machine step needs selection");
  assert.equal(await evaluate("document.getElementById('machine-status').textContent"), "Required");
  assert.equal(await evaluate("document.getElementById('market-status').textContent"), "Required for a setting");
  assert.equal(await evaluate("document.getElementById('search-status').textContent"), "Brand, formula name, or barcode");

  // ---- the payload column census ---------------------------------------
  // This block must stay last: it navigates the shared CDP target to an
  // instrumented copy of the page, so anything asserted after it would be
  // asserted against the wrong document.
  // The ratchet: every column packed into the page payload must be read by
  // the page. A column nothing consumes is dead weight shipped to every
  // visitor -- an `image_date` column rode along through a redesign that
  // stopped rendering it, 3,538 date literals and ~46KB, before this existed.
  //
  // Scope of the claim, deliberately narrow: this proves each packed index is
  // *accessed* while the page runs under the states driven below. It does not
  // claim the value renders, or that the column earns its bytes -- a mere
  // truthiness guard (`!r[9]`) counts as access. It is a location claim
  // ("nothing reads index N"), never a verdict that a column is well used.
  //
  // Runtime rather than static source parsing, by choice. A regex over the
  // emitted JS cannot tell an `r` bound to a record from an `r` bound to an
  // unavailable row -- the two schemas share the name and overlap in width --
  // and it goes quietly vacuous the moment the packing shape moves, which is
  // the worst failure a ratchet can have. This one fails the other way: loud,
  // naming the index and its column, and the only two ways to make it pass
  // are to delete the column or to drive the state that reads it. So every
  // payload column ends up carrying an end-to-end proof that it reaches the
  // page. The cost is honest and worth naming: a column read only in a state
  // nobody drives here reads as dead. That is the direction to fail in.
  const censusRoot = mkdtempSync(join(tmpdir(), "brezza-census-"));
  // Wrap every packed tuple before the page derives anything from it. HAY and
  // MASK are built from D.R two lines below this anchor, so instrumenting
  // after load would miss brand/type/stage/territories and need a hand-written
  // exemption for them -- exactly the quiet allowlist this test exists to
  // prevent. Numeric property reads are recorded; everything else passes
  // through untouched.
  const INSTRUMENT = `
const __census = {seen:{R:new Set(),V:new Set(),E:new Set(),U:new Set()},width:{},count:{}};
window.__census = __census;
(() => {
  const watch = (tuple, key) => new Proxy(tuple, {get(target, prop, receiver){
    if (typeof prop === "string" && String(+prop) === prop) __census.seen[key].add(+prop);
    return Reflect.get(target, prop, receiver);
  }});
  const census = (tuples, key) => {
    __census.count[key] = tuples.length;
    __census.width[key] = [...new Set(tuples.map(t => t.length))].sort((a,b) => a - b);
    return tuples.map(t => watch(t, key));
  };
  const variants = [], events = [];
  for (const row of D.R){
    if (row[9]) variants.push(...row[9]);
    if (row[10]) events.push(...row[10]);
  }
  const watchedVariants = census(variants, "V"), watchedEvents = census(events, "E");
  let vi = 0, ei = 0;
  for (const row of D.R){
    if (row[9]) row[9] = row[9].map(() => watchedVariants[vi++]);
    if (row[10]) row[10] = row[10].map(() => watchedEvents[ei++]);
  }
  D.R = census(D.R, "R");
  D.U = census(D.U || [], "U");
})();
`;
  const ANCHOR = "\nconst QUICK = ";
  const shipped = readFileSync(join(root, "site/index.html"), "utf8");
  assert.equal(shipped.split(ANCHOR).length - 1, 1,
    `The census anchor ${JSON.stringify(ANCHOR)} must appear exactly once in the built page`);
  const censusPage = join(censusRoot, "index.html");
  writeFileSync(censusPage, shipped.replace(ANCHOR, `\n${INSTRUMENT}\n${ANCHOR.trim()} `));
  await send("Page.navigate", { url: pathToFileURL(censusPage).href });
  for (let tries = 0; tries < 80; tries += 1) {
    try {
      if (await evaluate("document.readyState === 'complete' && typeof run === 'function' && !!window.__census")) break;
    } catch {}
    await pause(50);
  }
  assert.equal(await evaluate("!!window.__census"), true,
    "The instrumented copy of the page did not install the column recorder");

  // Every drive is written out from scratch -- the instrumented copy is a
  // different file:// document, so nothing carries over from the walk above.
  // Each one names the columns it exists to reach; deleting one silently
  // narrows the census, so treat these as the census's coverage argument.
  const censusDrive = async (fields, note) => {
    for (const [id, value] of fields) await setValue(id, value, "input");
    // A result card is where most columns are read; an ambiguous search stops
    // at choices, so settle it the way an owner would.
    if (await evaluate("out.querySelector('.rec.result') === null && out.querySelector('[data-choice]') !== null")) {
      await evaluate("out.querySelector('[data-choice]').click()");
      await settle();
    }
    assert.notEqual(await evaluate("out.innerHTML.length"), 0, `census drive rendered nothing: ${note}`);
  };
  await chooseMachine("advanced");
  // Albania carries all three schemas: a territory-variant record with its own
  // photo, `was` rows, and an unavailable row with a barcode.
  // barcode over both lists: R.upc on plain rows, V.territories + V.upc on the
  // variant rows, U.upc on the unavailable rows.
  await censusDrive([["terr", "Albania"], ["lot", "2200XYZ"], ["q", "8718117609512"]],
    "barcode in a market that holds a territory-variant record");
  // the resolved variant record: V.thumb comes only from rowThumb, and only on
  // a row where a variant matches the selected market.
  await censusDrive([["q", "aptamil ar 2 (switzerland)"]],
    "a resolved territory-variant record");
  assert.equal(await evaluate("out.querySelector('.rec.result .thumb').src.includes('4277-')"), true,
    "the variant drive must render the photo the selected variant carries, not the record's own");
  // a plain record with a struck-out `was`: R.was, R.thumb, R.events.
  await censusDrive([["q", "bebilon prosyneo ha hydrolyzed advance 3"]],
    "a record carrying a `was` chip");
  assert.equal(await evaluate("out.querySelector('.rec.result .was') !== null"), true,
    "the `was` drive must actually render a was chip, or it does not reach R.was");
  // the unavailable card: U.reason and U.thumb.
  await censusDrive([["q", "milupa"]], "a known-unavailable row");
  assert.equal(await evaluate("out.querySelector('.warning') !== null"), true,
    "the unavailable drive must render an unavailable card, or it does not reach U.reason");
  // the lot gate reads R.setting and R.alt_setting through both branches.
  await censusDrive([["lot", ""], ["terr", "United States of America"],
                     ["q", "bobbie organic gentle"]], "a lot-gated record");
  await censusDrive([["lot", "1123ABC"]], "the same record on a lot-11 machine");

  // Packed column order, from pack() in build_page.py. These names only label
  // the failure; the widths are read from the payload itself, so a stale name
  // here can never make a dead column pass.
  const COLUMNS = {
    R: ["brand", "type", "stage", "setting", "territories", "upc", "alt_setting",
        "was", "thumb", "variants", "events"],
    V: ["territories", "upc", "thumb"],
    E: ["observed", "field", "from", "to", "territory"],
    U: ["brand", "type", "stage", "territories", "reason", "upc", "thumb"],
  };
  const SCHEMA_NAMES = { R: "record", V: "territory variant", E: "setting-history event",
                         U: "known-unavailable row" };
  // Columns that legitimately ship unread. SHRINK-ONLY: entries may be removed,
  // never added. A column nothing reads is a column to delete, not one to park
  // here -- an addition is a change to the rule this test enforces, and has to
  // be argued as one rather than slipped in as a test fix.
  const UNREAD_ALLOWED = { R: [], V: [], E: [], U: [] };

  const census = await evaluate(`(() => { const c = window.__census; return {
    seen: Object.fromEntries(Object.entries(c.seen).map(([k,v]) => [k, [...v].sort((a,b) => a-b)])),
    width: c.width, count: c.count } })()`);
  for (const key of Object.keys(COLUMNS)) {
    const { [key]: names } = COLUMNS;
    const count = census.count[key], widths = census.width[key];
    if (count === 0) {
      // Nothing of this shape is packed, so there are no bytes to be dead. The
      // requirement re-arms by itself the moment the payload carries one --
      // which will need a drive above for it.
      console.log(`  column census: 0 ${SCHEMA_NAMES[key]} tuples packed; nothing to assert`);
      continue;
    }
    assert.equal(widths.length, 1,
      `${SCHEMA_NAMES[key]} tuples are packed at mixed widths ${JSON.stringify(widths)}; ` +
      "the census cannot say which column is which");
    const [width] = widths;
    assert.equal(width, names.length,
      `${SCHEMA_NAMES[key]} tuples are packed ${width} wide but COLUMNS.${key} names ` +
      `${names.length} (${names.join(", ")}). Update the names in this census to match pack().`);
    const unread = [];
    for (let i = 0; i < width; i += 1)
      if (!census.seen[key].includes(i) && !UNREAD_ALLOWED[key].includes(i)) unread.push(i);
    assert.deepEqual(unread, [], unread.map(i =>
      `Packed but never read: ${SCHEMA_NAMES[key]} column ${i} (${names[i] ?? "unnamed"}), ` +
      `shipped on ${count} tuple${count === 1 ? "" : "s"} of the payload. Either the page ` +
      "stopped reading it and pack() should stop packing it, or the state that reads it is " +
      "not driven in the census above.").join("\n"));
  }
  console.log(`  column census: ${Object.entries(census.count)
    .map(([k, n]) => `${k}=${census.width[k]?.[0] ?? 0}x${n}`).join(" ")} all columns read`);
  rmSync(censusRoot, { recursive: true, force: true });


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
