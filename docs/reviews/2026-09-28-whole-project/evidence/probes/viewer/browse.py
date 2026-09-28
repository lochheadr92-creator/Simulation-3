"""Load rendered viewer pages in headless Chromium, drive the UI, report console errors."""
import sys, json
from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

def probe(path):
    out = {"file": path, "errors": [], "pageerrors": [], "dialogs": []}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.on("console", lambda m: out["errors"].append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: out["pageerrors"].append(str(e)))
        pg.on("dialog", lambda d: (out["dialogs"].append(d.message), d.dismiss()))
        pg.goto("file://" + path)
        pg.wait_for_timeout(500)
        n = pg.evaluate("document.getElementById('slider').max")
        out["slider_max"] = n
        # step through several views, end, start
        for key in ["ArrowRight", "ArrowRight", "ArrowRight", "End", "Home"]:
            pg.keyboard.press(key); pg.wait_for_timeout(60)
        pg.evaluate("document.getElementById('slider').value = Math.floor(%s/2); document.getElementById('slider').dispatchEvent(new Event('input'))" % n)
        pg.wait_for_timeout(100)
        # inspector: click first event, then inspector tab
        if pg.locator("#events button.event").count():
            pg.locator("#events button.event").first.click(); pg.wait_for_timeout(60)
        pg.click("#tab-inspector"); pg.wait_for_timeout(80)
        out["inspector_text"] = pg.inner_text("#inspector")[:600]
        # deep section
        pg.evaluate("document.getElementById('deep').open = true; document.getElementById('deep').dispatchEvent(new Event('toggle'))")
        pg.wait_for_timeout(300)
        out["people_rows"] = pg.locator("#people tr").count()
        out["totals"] = pg.inner_text("#totals")[:400]
        # checkpoint buttons
        for bid in ("scored", "crossover", "contested"):
            if pg.locator("#" + bid).is_enabled(): pg.click("#" + bid); pg.wait_for_timeout(40)
        # play a moment
        pg.click("#play"); pg.wait_for_timeout(700); pg.click("#play")
        # layers toggle
        pg.click("#layers-btn"); pg.wait_for_timeout(50)
        for cb in pg.locator("#layers input[type=checkbox]").all()[:4]:
            cb.click(); pg.wait_for_timeout(30)
        pg.wait_for_timeout(200)
        out["title"] = pg.title()
        out["h1"] = pg.inner_text("h1")
        out["injected_img"] = pg.locator("img").count()
        out["injected_marker"] = pg.evaluate("window.__pwned || null")
        b.close()
    return out

if __name__ == "__main__":
    for path in sys.argv[1:]:
        print(json.dumps(probe(path), indent=1))
