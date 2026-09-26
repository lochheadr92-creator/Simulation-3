// Print a viewer page's event feed, as the live page builds it.
//
//   node tools/feed.js runs/aquarium.html            # everything that happened
//   node tools/feed.js runs/aquarium.html "gave|died" # only the lines you care about
const { chromium } = require('playwright');
const path = require('path');
const { pathToFileURL } = require('url');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(pathToFileURL(path.resolve(process.argv[2])).href, { waitUntil: 'load' });
  await page.waitForTimeout(400);
  const rows = await page.evaluate(() =>
    [...document.querySelectorAll('#events .event')].map(b => b.textContent.replace(/\s+/g, ' ').trim()));
  const needle = new RegExp(process.argv[3] || '.', 'i');
  const hit = rows.filter(r => needle.test(r));
  console.log('events ' + rows.length + ', matching ' + hit.length);
  hit.forEach(r => console.log('  ' + r));
  await browser.close();
})();
