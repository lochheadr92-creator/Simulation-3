// Real DOM regression, including the initially closed deep section.
// Install dependencies with npm ci. Windows uses installed Edge by default;
// elsewhere use `npx playwright install chromium`, or set V3_BROWSER_CHANNEL.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const channel = process.env.V3_BROWSER_CHANNEL || (process.platform === 'win32' ? 'msedge' : undefined);
  const browser = await chromium.launch({ headless: true, ...(channel ? { channel } : {}) });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.argv[2], { waitUntil: 'load' });
    await page.locator('#deep > summary').click();
    await page.waitForFunction(() => document.querySelector('#totals').textContent.includes('deaths'));
    const checked = await page.evaluate(id => ({
      literal_id_visible: document.querySelector('#totals').textContent.includes(id),
      injected_elements: document.querySelectorAll('#totals img, #totals script, #totals [onerror]').length,
      executed: window.__viewer_xss ?? window.__pwned ?? null,
    }), process.argv[3]);
    // Step and scrub after opening: inspect the second dynamic presentation path.
    await page.locator('#next').click();
    assert((await page.locator('#selection').textContent()).includes(process.argv[3]));
    assert((await page.locator('#selection').textContent()).startsWith('Decision tick 0'));
    assert((await page.locator('#tick').textContent()).startsWith('World tick 1'));
    assert((await page.locator('body').textContent()).includes('consistency only'));
    checked.page_errors = errors;
    console.log(JSON.stringify(checked));
    assert.equal(checked.injected_elements, 0, 'actor id became an HTML element');
    assert.equal(checked.executed, null, 'actor id executed script');
    assert.equal(checked.literal_id_visible, true, 'actor id was not displayed literally');
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
