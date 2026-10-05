#!/usr/bin/env python3
"""Read ts_token.json (fresh Turnstile from solve_ts.py) and register the Sirius identity."""
import json
import os
import time
import uuid

import sirius_api as S

HERE = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(HERE, "ts_token.json")
tok = json.load(open(p))["token"]
print("token age: %.0fs (len %d)" % (time.time() - os.path.getmtime(p), len(tok)))

ident = os.urandom(32).hex()
inst = str(uuid.uuid4())
body = {"identityId": ident, "installationId": inst, "platform": "android",
        "avatarCode": "AVATAR_01"}
c = S.Sirius()
r = c.call("POST", "/auth/register", body=body, extra={"X-Turnstile-Token": tok})
print("register ->", json.dumps(r.get("body", r), default=str)[:500])

data = (r.get("body") or {}).get("data") or {}
if data.get("accessToken"):
    ap = os.path.join(HERE, "accounts.json")
    old = json.load(open(ap)) if os.path.exists(ap) else {}
    old[ident[:12]] = {"identityId": ident, "installationId": inst, "platform": "android",
                       "avatarCode": "AVATAR_01", "session": data}
    json.dump(old, open(ap, "w"), indent=1)
    os.chmod(ap, 0o600)
    print("AKUN DIBUAT -> tersimpan di", ap)
    print("identity:", ident)
    print("kursi/ref:", data.get("referralCode"), data.get("referralCount"))
else:
    print("BELUM berhasil — cek pesan di atas")
