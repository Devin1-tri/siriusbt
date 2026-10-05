#!/usr/bin/env python3
"""Solve the /auth/register Turnstile then register immediately (token is one-shot, ~5 min TTL).

Widget constraints learned the hard way:
 - the sitekey refuses `localhost` -> title ERR (error-callback code)
 - it ACCEPTS the hostname api.siriussrt.com served locally (Firefox network.dns.localDomains
   maps it to 127.0.0.1), and the challenge itself egresses through WARP
 - the solve can take ~80s, so wait patiently before giving up
"""
import asyncio
import json
import os
import time
import uuid

import requests
from camoufox.async_api import AsyncCamoufox

import sirius_api as S

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = "http://api.siriussrt.com:8002/index.html"
BYPASS = "localhost,127.0.0.1,api.siriussrt.com"
PROXY = {"server": "socks5://127.0.0.1:25344", "bypass": BYPASS}
PREFS = {"network.dns.localDomains": "api.siriussrt.com",
         "network.proxy.no_proxies_on": BYPASS.replace(",", ", ")}


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


async def solve(max_wait=200):
    async with AsyncCamoufox(headless=False, humanize=True, os="linux", geoip=False,
                             i_know_what_im_doing=True, proxy=PROXY,
                             firefox_user_prefs=PREFS,
                             args=["--window-size=1250,900"]) as browser:
        ctx = browser if hasattr(browser, "pages") else await browser.new_context()
        page = await ctx.new_page()
        await page.goto(PAGE, wait_until="domcontentloaded", timeout=90000)
        log("page:", page.url[:52])
        t0 = time.time()
        while time.time() - t0 < max_wait:
            await page.wait_for_timeout(2500)
            try:
                tok = await page.evaluate("window.TOKEN || ''")
                err = await page.evaluate("window.ERR || ''")
            except Exception:
                tok, err = "", ""
            if tok:
                log(f"TOKEN OK setelah {time.time()-t0:.0f}s (len {len(tok)})")
                return tok
            if err:
                log("widget tolak, kode:", err)
                return ""
            el = time.time() - t0
            if int(el) % 20 < 3:
                log(f"  nunggu {el:.0f}s")
        return ""


def register(token):
    ident = os.urandom(32).hex()
    inst = str(uuid.uuid4())
    body = {"identityId": ident, "installationId": inst, "platform": "android",
            "avatarCode": "AVATAR_01"}
    c = S.Sirius()
    r = c.call("POST", "/auth/register", body=body, extra={"X-Turnstile-Token": token})
    log("register:", json.dumps(r.get("body", r), default=str)[:400])
    data = (r.get("body") or {}).get("data") or {}
    if data.get("accessToken"):
        p = f"{HERE}/accounts.json"
        old = json.load(open(p)) if os.path.exists(p) else {}
        old[ident[:12]] = {"identityId": ident, "installationId": inst, "platform": "android",
                           "avatarCode": "AVATAR_01", "session": data}
        json.dump(old, open(p, "w"), indent=1)
        os.chmod(p, 0o600)
        log("AKUN DIBUAT ✓ identity:", ident[:16], "-> simpan", p)
        log("referralCode:", data.get("referralCode") or data.get("refCode") or "-",
            "| refs:", data.get("referralCount"))
    return data


async def main():
    tok = await solve()
    if not tok:
        log("gagal dapat token")
        return
    register(tok)


asyncio.run(main())
