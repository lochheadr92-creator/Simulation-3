// usage: node inspector_sections.cjs page.html step
// Visits every person at every `step` ticks through the page's own link, and lists the section headings the inspector showed.
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [pageArg, stepArg] = process.argv.slice(2);
  const step = Number(stepArg) || 20;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('pageerror', e => errors.push('page: ' + e.message));
  await page.goto('file://' + path.resolve(pageArg), { waitUntil: 'load' });
  await page.waitForTimeout(400);
  const info = await page.evaluate(() => { const s = window.viewerState(); return { ticks: s.ticks, people: s.people.length }; });
  const roster = await page.evaluate(() => [...document.querySelectorAll('#events .event')].length >= 0 ? null : null);
  const people = await page.evaluate(() => Array.from(new Set((document.getElementById('run-data').textContent.match(/"p\d\d"/g) || []))).map(x => x.slice(1, -1)).sort());
  const headings = {};
  for (let k = 0; k <= info.ticks; k += step) {
    for (const p of people) {
      await page.evaluate(([k2, p2]) => { location.hash = `#v=${k2}&p=${p2}`; }, [k, p]);
      await page.waitForTimeout(12);
      const found = await page.evaluate(() => [...document.querySelectorAll('#inspector h4')].map(h => h.textContent.trim()));
      for (const h of found) (headings[h] = headings[h] || []).push(`${p}@${k}`);
    }
  }
  await browser.close();
  process.stdout.write(JSON.stringify({ errors, headings: Object.fromEntries(Object.entries(headings).map(([h, at]) => [h, at.slice(0, 3)])) }));
})().catch(e => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
