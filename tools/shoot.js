// Open a viewer page in a real browser, click through it, and save screenshots.
//
//   node tools/shoot.js runs/aquarium.html out/dir [tick ...]
//
// Loads the page, fails loudly on any console error or page exception, and
// writes one PNG per tick asked for, plus a shot of the whole page.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const [pageArg, outArg, ...tickArgs] = process.argv.slice(2);
if (!pageArg || !outArg) {
  console.error('usage: node tools/shoot.js <page.html> <out-dir> [tick ...]');
  process.exit(2);
}
const ticks = tickArgs.length ? tickArgs.map(Number) : [0];
fs.mkdirSync(outArg, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  const problems = [];
  page.on('console', m => { if (m.type() === 'error') problems.push('console error: ' + m.text()); });
  page.on('pageerror', e => problems.push('page error: ' + e.message));

  await page.goto('file://' + path.resolve(pageArg).replace(/\\/g, '/'), { waitUntil: 'load' });
  await page.waitForTimeout(400);

  // what the page actually built, read back out of the live DOM
  const built = await page.evaluate(() => ({
    title: document.querySelector('h1') ? document.querySelector('h1').textContent : '(none)',
    events: document.querySelectorAll('#events .event').length,
    firstEvents: [...document.querySelectorAll('#events .event')].slice(0, 5)
      .map(b => b.textContent.replace(/\s+/g, ' ').trim()),
    people: document.querySelectorAll('#people tr').length,
    hovers: document.querySelectorAll('#map title').length,
    tick: document.getElementById('tick').textContent,
  }));
  console.log('title       :', built.title);
  console.log('event rows  :', built.events);
  console.log('people rows :', built.people);
  console.log('hover titles:', built.hovers);
  console.log('tick label  :', built.tick);
  console.log('first events:'); built.firstEvents.forEach(e => console.log('   ' + e));

  for (const t of ticks) {
    await page.evaluate(k => show(k), t);
    await page.waitForTimeout(150);
    const file = path.join(outArg, `tick-${String(t).padStart(4, '0')}.png`);
    await page.locator('#map').screenshot({ path: file });
    console.log('wrote', file);
  }
  const whole = path.join(outArg, 'page.png');
  await page.screenshot({ path: whole, fullPage: false });
  console.log('wrote', whole);

  await browser.close();
  if (problems.length) { console.error('\nPROBLEMS:'); problems.forEach(p => console.error('  ' + p)); process.exit(1); }
  console.log('\nno console errors, no page exceptions');
})();
