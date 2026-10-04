// Drives a rich-world page through its real controls and prints what the inspector shows.
//   node rich_viewer.cjs page.html tick person
// Install dependencies with npm ci; see tests/fixtures/viewer_security.cjs for browser setup.
const { chromium } = require('playwright');

(async () => {
  const channel = process.env.V3_BROWSER_CHANNEL || (process.platform === 'win32' ? 'msedge' : undefined);
  const browser = await chromium.launch({ headless: true, ...(channel ? { channel } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    await page.goto(process.argv[2], { waitUntil: 'load' });
    const [tick, person] = [process.argv[3], process.argv[4]];
    // select through the page's own happenings list, then move to the tick through the slider
    await page.evaluate(p => {
      const row = [...document.querySelectorAll('#events button, #events .event')].find(b => b.textContent.includes(p));
      if (row) row.click();
    }, person);
    await page.evaluate(k => { const s = document.getElementById('slider'); s.value = k; s.dispatchEvent(new Event('input', { bubbles: true })); }, tick);
    await page.locator('#tab-inspector').click();
    const out = await page.evaluate(() => ({
      inspector: document.getElementById('inspector').innerText,
      chips: [...document.querySelectorAll('.chip.switch')].map(c => c.textContent),
      focus: document.getElementById('focus-what').textContent,
      tickLabel: document.getElementById('tick').textContent,
      eventCategories: [...document.querySelectorAll('#cats *')].map(c => c.textContent),
      rules: document.querySelector('.rules') ? document.querySelector('.rules').textContent : '',
    }));
    out.errors = errors;
    console.log(JSON.stringify(out));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
