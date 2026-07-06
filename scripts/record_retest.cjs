// Record a short screen video of a retest flow using Playwright (recordVideo).
// CommonJS so `require('playwright')` honors NODE_PATH (point it at the app's node_modules).
//
// Usage: NODE_PATH=<app>/node_modules node record_retest.cjs <stepsJsonFile> <outDir>
//   steps JSON: [{ "do":"goto","url":"..." },
//                { "do":"fill","selector":"input[name=password]","value":"..." },
//                { "do":"click","selector":"button:has-text('Log In')" },
//                { "do":"wait","ms":1200 },
//                { "do":"waitFor","selector":"text=Stations" }]
// Prints the final video path on stdout (last line).
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const { chromium } = require('playwright');
  const [stepsFile, outDir] = process.argv.slice(2);
  if (!stepsFile || !outDir) { console.error('usage: record_retest.cjs <stepsJsonFile> <outDir>'); process.exit(1); }
  fs.mkdirSync(outDir, { recursive: true });
  const steps = JSON.parse(fs.readFileSync(stepsFile, 'utf8'));

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: { dir: outDir, size: { width: 1280, height: 720 } },
  });
  const page = await context.newPage();
  try {
    for (const s of steps) {
      if (s.do === 'goto') await page.goto(s.url, { waitUntil: 'domcontentloaded' });
      else if (s.do === 'fill') await page.fill(s.selector, s.value);
      else if (s.do === 'type') await page.type(s.selector, s.value, { delay: 40 });
      else if (s.do === 'click') await page.click(s.selector);
      else if (s.do === 'press') await page.press(s.selector || 'body', s.key);
      else if (s.do === 'wait') await page.waitForTimeout(s.ms || 1000);
      else if (s.do === 'waitFor') await page.waitForSelector(s.selector, { timeout: s.timeout || 8000 }).catch(() => {});
      await page.waitForTimeout(300);
    }
  } catch (e) {
    console.error('step error:', e.message);
  } finally {
    const video = page.video();
    await context.close(); // flush video
    await browser.close();
    const file = video ? await video.path() : null;
    if (!file || !fs.existsSync(file)) { console.error('no video produced'); process.exit(2); }
    console.log(path.resolve(file));
  }
})();
