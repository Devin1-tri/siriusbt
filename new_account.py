#!/usr/bin/env python3
"""Create a new Sirius account end-to-end: Turnstile -> register -> bind -> mine.

The Turnstile solve runs in the `cfsolve` venv (it has camoufox but no
`cryptography`), the API side runs here (`bot/.venv` has `cryptography`) -- the
token is one-shot with a ~5 min TTL, so the two are chained inside one call.

Usage:  ./sirius.sh new [INVITE_CODE]     (default: SIRIUS_INVITE / f34UvL)
"""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

import sirius_api as S
from sirius_session import accounts_lock, session_for

HERE = os.path.dirname(os.path.abspath(__file__))
CFSOLVE = "/home/ubuntu/bot/cfsolve/bin/python"
TOKEN = os.path.join(HERE, "ts_token.json")
INVITE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SIRIUS_INVITE", "f34UvL")


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def solve_turnstile():
    if os.path.exists(TOKEN):
        os.remove(TOKEN)
    env = dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":99"))
    log("solve Turnstile (bisa 10-250 detik)...")
    p = subprocess.run([CFSOLVE, "solve_ts.py"], cwd=HERE, env=env,
                       capture_output=True, text=True, timeout=540)
    for line in (p.stdout or "").splitlines()[-4:]:
        if line.strip():
            print("   ", line, flush=True)
    if not os.path.exists(TOKEN):
        log("gagal dapat token:", (p.stderr or "")[-300:])
        return ""
    age = time.time() - os.path.getmtime(TOKEN)
    tok = json.load(open(TOKEN)).get("token", "")
    log(f"token siap (age {age:.0f}s, len {len(tok)})")
    return tok


def register(tok):
    ident = os.urandom(32).hex()
    inst = str(uuid.uuid4())
    body = {"identityId": ident, "installationId": inst,
            "platform": "android", "avatarCode": "AVATAR_01"}
    r = S.Sirius().call("POST", "/auth/register", body=body,
                        extra={"X-Turnstile-Token": tok})
    data = (r.get("body") or {}).get("data") or {}
    if not data.get("accessToken"):
        log("register GAGAL:", json.dumps(r.get("body"), default=str)[:300])
        return None, None
    with accounts_lock() as accts:
        accts[ident[:12]] = {"identityId": ident, "installationId": inst,
                             "platform": "android", "avatarCode": "AVATAR_01",
                             "session": data}
    log("akun dibuat:", ident[:12], "| userCode", data.get("userCode"))
    return ident[:12], data


def main():
    if not os.path.exists(CFSOLVE):
        log("solver tidak ada:", CFSOLVE)
        return 1
    tok = solve_turnstile()
    if not tok:
        return 2
    if time.time() - os.path.getmtime(TOKEN) > 240:
        log("token terlalu tua untuk dipakai, solve ulang")
        return 2
    key, _ = register(tok)
    if not key:
        return 3

    with accounts_lock() as accts:
        client, key = session_for(accts, key)
        if not client:
            log("session gagal untuk akun baru")
            return 4
        inv = client.call("POST", "/users/me/inviter", body={"inviterCode": INVITE})
        log("bind:", json.dumps((inv.get("body") or {}).get("data"), default=str)[:160])
        st = client.call("POST", "/mining/tasks/start", body={})
        d = (st.get("body") or {}).get("data") or {}
        log("mining:", d.get("roundId") or json.dumps(st.get("body"), default=str)[:200],
            "->", d.get("endsAt"))
    log("SELESAI — jalankan ./sirius.sh status untuk lihat", key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
