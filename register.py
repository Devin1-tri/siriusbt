#!/usr/bin/env python3
"""Sirius: solve the register Turnstile, then create the identity.

The app renders turnstile.render('#challenge', {sitekey, action:'register'}) in a local
WebView ("https://localhost/turnstile-test/"), so the widget allows the `localhost` host:
we serve the same widget on http://localhost:8002/ and let the local captcha solver
(global-captcha, :8001) produce the token, which /auth/register wants in X-Turnstile-Token.
"""
import json
import os
import time
import uuid

import requests

import sirius_api as S

SITEKEY = "0x4AAAAAAE4Yb4FqKM_qx4B1"
PAGE = "http://localhost:8002/index.html"
SOLVER = "http://127.0.0.1:8001"


def solve(action="register", timeout=180):
    r = requests.get(f"{SOLVER}/turnstile",
                     params={"url": PAGE, "sitekey": SITEKEY, "action": action}, timeout=30)
    print("  solve start:", r.status_code, r.text[:120])
    tid = r.json().get("task_id")
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(3)
        rr = requests.get(f"{SOLVER}/result", params={"id": tid}, timeout=30)
        try:
            d = rr.json()
        except Exception:
            continue
        tok = d.get("token") or d.get("turnstile_token")
        if tok:
            return tok
        if d.get("status") in ("error", "failed"):
            print("  solve gagal:", rr.text[:200])
            return None
    return None


def main():
    print("== 1. solve turnstile (action=register) ==")
    tok = solve()
    print("  token:", (tok or "NONE")[:50], "... len", len(tok or ""))
    if not tok:
        return 1

    ident = os.urandom(32).hex()          # Sirius ID = 64-char identifier
    inst = str(uuid.uuid4())
    body = {"identityId": ident, "installationId": inst, "platform": "android",
            "avatarCode": "AVATAR_01"}
    print("\n== 2. POST /auth/register ==")
    c = S.Sirius()
    r = c.call("POST", "/auth/register", body=body, extra={"X-Turnstile-Token": tok})
    print("  ", json.dumps(r, default=str)[:500])

    data = (r.get("body") or {}).get("data") or {}
    if data.get("accessToken"):
        store = {"identityId": ident, "installationId": inst, "platform": "android",
                 "avatarCode": "AVATAR_01", "register": data}
        p = "/home/ubuntu/bot/sirius/accounts.json"
        old = json.load(open(p)) if os.path.exists(p) else {}
        old[ident[:12]] = store
        json.dump(old, open(p, "w"), indent=1)
        os.chmod(p, 0o600)
        print("  AKUN DIBUAT ✓ identity:", ident[:16], "| token disimpan ke", p)
        print("  accessToken:", str(data.get("accessToken"))[:24], "... refs:",
              data.get("referralCode") or data.get("refCode"))
    return 0


raise SystemExit(main())
