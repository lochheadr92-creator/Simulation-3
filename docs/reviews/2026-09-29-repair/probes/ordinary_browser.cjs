// Run from the source root; uses that checkout's locked Playwright install.
const { chromium } = require(require.resolve('playwright', {paths:[process.cwd()]}));
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const channel=process.env.V3_BROWSER_CHANNEL || (process.platform==='win32'?'msedge':undefined);
  const browser = await chromium.launch({headless:true,...(channel?{channel}:{})});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.argv[2]);
    const index=await page.evaluate(()=>JSON.parse(document.querySelector('#view-index').textContent));
    const i=index.events.findIndex(e=>e.kind==='remembered_helper' && e.who==='p27' && e.k===714);
    assert(i>=0);
    await page.locator(`.event[data-i="${i}"]`).click();
    assert((await page.locator('#tick').textContent()).startsWith('World tick 714'));
    await page.locator('#deep > summary').click();
    const row=await page.locator('#people tr').evaluateAll(rows=>rows.find(r=>r.firstElementChild.textContent==='p27').textContent);
    assert(row.includes('p19 gave me food at tick 560'));
    assert((await page.locator('#selection').textContent()).startsWith('Decision tick 713'));
    await page.locator('#deep > summary').click();
    await page.screenshot({path:process.argv[3]});
    const result={world_tick:714,decision_tick:713,person:'p27',native_return_gift_reason_visible:true,page_errors:errors};
    fs.writeFileSync(process.argv[4],JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
    assert.deepEqual(errors,[]);
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
