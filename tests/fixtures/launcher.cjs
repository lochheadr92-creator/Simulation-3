// usage: node launcher.cjs http://127.0.0.1:PORT
// Opens the launcher page, starts a short world through its real controls, waits for it to finish and reports what is on screen.
const { chromium } = require('playwright');
(async () => {
  const base = process.argv[2];
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('pageerror', e => errors.push('page: ' + e.message));
  await page.goto(base + '/', { waitUntil: 'load' });
  await page.waitForFunction(() => document.querySelectorAll('#scenes .scene').length > 0 && document.querySelectorAll('#features input').length > 0);
  const scenes = await page.evaluate(() => document.querySelectorAll('#scenes .scene').length);
  const features = await page.evaluate(() => document.querySelectorAll('#features input').length);
  await page.click('#scenes .scene');                       // the first scene: the plain world
  await page.fill('#ticks', '30');
  await page.click('#go');
  await page.waitForFunction(() => document.getElementById('status').textContent.startsWith('Finished'), null, { timeout: 120000 });
  // a finished world is loaded once more at the end, so wait for that last load before looking inside the viewer
  await page.waitForFunction(() => { const f = document.getElementById('view'); try { return f.contentWindow.location.href.includes('done=1') && !!f.contentDocument.getElementById('minimap'); } catch (e) { return false; } }, null, { timeout: 60000 });
  const frame = page.frames().find(f => f !== page.mainFrame() && f.url().includes('done=1'));
  const out = {
    errors, scenes, features,
    status: await page.textContent('#status'),
    viewerHasMinimap: !!(await frame.$('#minimap')),
    runs: await page.evaluate(() => document.querySelectorAll('#runs > div').length),
  };
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})().catch(e => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
