// Load a viewer page and print whatever it complains about.
//   node tools/why.js runs/aquarium.html [tick]
const { chromium } = require('playwright');
const path = require('path');
const { pathToFileURL } = require('url');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('page error: ' + e.stack.split('\n').slice(0, 3).join('\n    ')));
  page.on('console', m => { if (m.type() === 'error') console.log('console error: ' + m.text()); });
  await page.goto(pathToFileURL(path.resolve(process.argv[2])).href, { waitUntil: 'load' });
  await page.waitForTimeout(400);
  if (process.argv[3]) {
    const out = await page.evaluate(k => { try { show(k); return 'ok'; } catch (e) { return e.stack.split('\n').slice(0, 3).join(' | '); } },
      Number(process.argv[3]));
    console.log('show(' + process.argv[3] + '): ' + out);
  }
  await browser.close();
})();
