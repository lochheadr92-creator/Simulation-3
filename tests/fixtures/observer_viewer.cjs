// usage: node observer_viewer.cjs page.html eventText
// Drives the observer tools through the page's real controls and prints what they did as JSON.
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [pageArg, cellEvent] = process.argv.slice(2);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('pageerror', e => errors.push('page: ' + e.message));
  const url = 'file://' + path.resolve(pageArg);
  const out = { errors };
  // a link that remembers the tick and the person
  await page.goto(url + '#v=60&p=p01', { waitUntil: 'load' });
  await page.waitForTimeout(500);
  out.opened = await page.evaluate(() => window.viewerState());
  // the minimap moves the camera and nothing else
  const before = await page.evaluate(() => window.viewerState());
  const box = await page.locator('#minimap').boundingBox();
  await page.mouse.click(box.x + box.width * 0.12, box.y + box.height * 0.12);
  await page.waitForTimeout(250);
  const after = await page.evaluate(() => window.viewerState());
  out.minimap = { moved: Math.abs(after.camera.x - before.camera.x) + Math.abs(after.camera.y - before.camera.y) > 1, sameView: after.view === before.view, sameSelection: JSON.stringify(after.selected) === JSON.stringify(before.selected) };
  // speed and camera do not change what is shown for a tick
  const shown = async () => page.evaluate(() => ({ view: window.viewerState().view, hud: document.getElementById('hud-line').innerText, tick: document.getElementById('tick').innerText, inspector: document.getElementById('inspector').innerText }));
  const readings = [];
  for (const speed of ['1', '32', '4']) {
    await page.selectOption('#speed', speed);
    await page.evaluate(() => window.show(90));
    await page.waitForTimeout(150);
    await page.click('#fit');
    await page.waitForTimeout(150);
    readings.push(await shown());
  }
  out.speedIndependent = readings.every(r => JSON.stringify(r) === JSON.stringify(readings[0]));
  // fog and headings draw for the selected person without trouble
  for (const key of ['fog', 'heading']) await page.evaluate(k => { const el = document.querySelector(`[data-layer="${k}"]`); el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); }, key);
  for (const k of [0, 30, 120, 200]) { await page.evaluate(k2 => window.show(k2), k); await page.waitForTimeout(80); }
  await page.evaluate(() => window.show(40));       // scrubbing back rebuilds what they had seen
  await page.waitForTimeout(150);
  const state = await page.evaluate(() => window.viewerState());
  out.layers = state.layers; out.fogAt40 = state.fog;
  await page.evaluate(() => window.show(150)); await page.waitForTimeout(100);
  out.fogAt150 = (await page.evaluate(() => window.viewerState())).fog;
  // an event with a place rings that place
  if (cellEvent) {
    await page.click('#tab-events');
    const ok = await page.evaluate(kind => { const rows = [...document.querySelectorAll('#events button.event')]; const row = rows.find(r => r.textContent.includes(kind)); if (!row) return false; row.click(); return true; }, cellEvent);
    await page.waitForTimeout(250);
    out.eventClicked = ok;
    out.place = (await page.evaluate(() => window.viewerState())).placeMark;
  }
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})().catch(e => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
