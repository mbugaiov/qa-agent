// Record a short screen video of a retest flow using Playwright (recordVideo).
// CommonJS so `require('playwright')` honors NODE_PATH (point it at the app's node_modules).
//
// Usage: NODE_PATH=<app>/node_modules node record_retest.cjs <stepsJsonFile> <outDir>
//   steps JSON (legacy array):
//     [{ "do":"goto","url":"..." }, { "do":"click","selector":"..." }, ...]
//   steps JSON (object — preferred when the flow must stay authenticated):
//     {
//       "expectAuthenticated": true,
//       "unauthenticated": { "urlIncludes": "/sign-in", "selector": "[name=email]" },
//       "steps": [ ... ]
//     }
//   `protected: true` is an alias for `expectAuthenticated`.
//   When expectAuthenticated/protected is set, at least one of
//   unauthenticated.urlIncludes or unauthenticated.selector is required (project-
//   specific; never hardcoded in this engine script). Exit 3 if the page matches.
// Prints the final video path on stdout (last line).
const fs = require('node:fs');
const path = require('node:path');

function loadStepsDoc(raw) {
  const data = JSON.parse(raw);
  if (Array.isArray(data)) {
    return { steps: data, expectAuthenticated: false, unauthenticated: {} };
  }
  if (data && typeof data === 'object' && Array.isArray(data.steps)) {
    return {
      steps: data.steps,
      expectAuthenticated: !!(data.expectAuthenticated || data.protected),
      unauthenticated: data.unauthenticated && typeof data.unauthenticated === 'object'
        ? data.unauthenticated
        : {},
    };
  }
  throw new Error('steps JSON must be an array or { steps: [...] }');
}

async function landedUnauthenticated(page, unauthenticated) {
  const urlInc = unauthenticated.urlIncludes;
  const sel = unauthenticated.selector;
  if (urlInc && typeof urlInc === 'string' && page.url().includes(urlInc)) return true;
  if (sel && typeof sel === 'string') {
    if (await page.locator(sel).isVisible().catch(() => false)) return true;
  }
  return false;
}

(async () => {
  const { chromium } = require('playwright');
  const [stepsFile, outDir] = process.argv.slice(2);
  if (!stepsFile || !outDir) { console.error('usage: record_retest.cjs <stepsJsonFile> <outDir>'); process.exit(1); }
  fs.mkdirSync(outDir, { recursive: true });
  let doc;
  try {
    doc = loadStepsDoc(fs.readFileSync(stepsFile, 'utf8'));
  } catch (e) {
    console.error('steps JSON error:', e.message);
    process.exit(1);
  }
  const { steps, expectAuthenticated, unauthenticated } = doc;
  if (expectAuthenticated) {
    const hasUrl = typeof unauthenticated.urlIncludes === 'string' && unauthenticated.urlIncludes.length > 0;
    const hasSel = typeof unauthenticated.selector === 'string' && unauthenticated.selector.length > 0;
    if (!hasUrl && !hasSel) {
      console.error(
        'expectAuthenticated/protected requires unauthenticated.urlIncludes and/or unauthenticated.selector in the steps file'
      );
      process.exit(1);
    }
  }

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: { dir: outDir, size: { width: 1280, height: 720 } },
  });
  const page = await context.newPage();
  let authRejected = false;
  try {
    for (const s of steps) {
      if (s.do === 'goto') await page.goto(s.url, { waitUntil: 'domcontentloaded' });
      else if (s.do === 'fill') await page.fill(s.selector, s.value);
      else if (s.do === 'type') await page.type(s.selector, s.value, { delay: 40 });
      else if (s.do === 'click') await page.click(s.selector);
      else if (s.do === 'clickIfVisible') {
        const loc = page.locator(s.selector);
        if (await loc.isVisible().catch(() => false)) await loc.click();
      }
      else if (s.do === 'press') await page.press(s.selector || 'body', s.key);
      else if (s.do === 'wait') await page.waitForTimeout(s.ms || 1000);
      else if (s.do === 'waitFor') await page.waitForSelector(s.selector, { timeout: s.timeout || 8000 }).catch(() => {});
      await page.waitForTimeout(300);
    }
    // Reject recordings that land unauthenticated when the steps file opts in.
    if (expectAuthenticated && await landedUnauthenticated(page, unauthenticated)) {
      console.error('recording ended unauthenticated; add login steps or storageState');
      authRejected = true;
    }
  } catch (e) {
    console.error('step error:', e.message);
  } finally {
    const video = page.video();
    await context.close(); // flush video
    await browser.close();
    if (authRejected) process.exit(3);
    const file = video ? await video.path() : null;
    if (!file || !fs.existsSync(file)) { console.error('no video produced'); process.exit(2); }
    console.log(path.resolve(file));
  }
})();
