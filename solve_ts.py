#!/usr/bin/env python3
"""Turnstile for /auth/register — widget must run on an allowlisted hostname.

The sitekey refuses `localhost` (title ERR), so we serve the same page locally but make
Firefox resolve api.siriussrt.com to 127.0.0.1 (network.dns.localDomains) and load it as
http://api.siriussrt.com:8002/index.html — CF matches the hostname, ports are ignored.
The CF widget traffic itself egresses through WARP (Cloudflare-owned IP range).
"""
import asyncio
import json
import os
import time

from camoufox.async_api import AsyncCamoufox

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = "http://api.siriussrt.com:8002/index.html"
BYPASS = "localhost,127.0.0.1,api.siriussrt.com"
PROXY = {"server": "socks5://127.0.0.1:25344", "bypass": BYPASS}
PREFS = {
    "network.dns.localDomains": "api.siriussrt.com",
    "network.proxy.no_proxies_on": BYPASS.replace(",", ", "),
}


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


async def main():
    async with AsyncCamoufox(headless=False, humanize=True, os="linux", geoip=False,
                             i_know_what_im_doing=True, proxy=PROXY,
                             firefox_user_prefs=PREFS,
                             args=["--window-size=1250,900"]) as browser:
        ctx = browser if hasattr(browser, "pages") else await browser.new_context()
        page = await ctx.new_page()
        await page.goto(PAGE, wait_until="domcontentloaded", timeout=90000)
        log("url:", page.url[:60], "| title:", (await page.title())[:30])
        token = ""
        for i in range(150):       # managed challenge from this IP has taken 80-205s
            await page.wait_for_timeout(2500)
            try:
                token = await page.evaluate(
                    "window.TOKEN || document.getElementById('out').textContent || ''")
                err = await page.evaluate("window.ERR || ''")
                ttl = await page.title()
            except Exception:
                token, err, ttl = "", "", ""
            if ttl.startswith("TOKEN_READY") and not token:
                token = await page.evaluate("window.TOKEN || ''")
            if token:
                break
            if err:
                log("widget menolak, kode:", err, "-> berhenti")
                break
            if i in (3, 10, 18):
                box = await page.evaluate("""(function(){
                    var f=document.querySelector('#challenge iframe')||document.querySelector('iframe');
                    if(!f) return ''; var r=f.getBoundingClientRect();
                    return JSON.stringify({x:r.x+28,y:r.y+r.height/2});})()""")
                if box:
                    d = json.loads(box)
                    await page.mouse.move(d["x"], d["y"], steps=8)
                    await page.wait_for_timeout(400)
                    await page.mouse.click(d["x"], d["y"])
                    log(f"klik widget di {d}")
            if i % 4 == 0:
                log(f"  nunggu {i*2.5:.0f}s")
        log("TOKEN:", (token or "NONE")[:60], "len", len(token or ""))
        if token:
            json.dump({"token": token}, open(f"{HERE}/ts_token.json", "w"))
            log("saved ts_token.json")
        await page.screenshot(path=f"{HERE}/ts_solve.png")


asyncio.run(main())
