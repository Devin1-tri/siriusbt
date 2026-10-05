#!/usr/bin/env python3
"""Read-only status for every account: mining round, referral binding, overview."""
import json
import os

import sirius_api as S

HERE = os.path.dirname(os.path.abspath(__file__))
ACC = os.path.join(HERE, "accounts.json")


def show(tag, r):
    body = (r.get("body") if isinstance(r, dict) else r) or {}
    print(f"[{tag}] {r.get('_status')} {json.dumps(body, default=str)[:320]}", flush=True)
    return body


def session_for(acct):
    """Fresh access token: try refresh (single-use) then device login."""
    sess = acct["session"]
    c = S.Sirius()
    r = c.call("POST", "/auth/refresh", body={"refreshToken": sess["refreshToken"]})
    data = (r.get("body") or {}).get("data") or {}
    if not data.get("accessToken"):
        r = c.call("POST", "/auth/login", body={"identityId": acct["identityId"],
                                                 "installationId": acct["installationId"],
                                                 "platform": acct["platform"]})
        data = (r.get("body") or {}).get("data") or {}
    if not data.get("accessToken"):
        print("[auth] GAGAL", json.dumps(r.get("body"), default=str)[:200])
        return None, None
    sess.update(data)
    json.dump(json.load(open(ACC)), open(ACC, "w"), indent=1)  # keep rotation on disk
    accounts = json.load(open(ACC))
    for k, v in accounts.items():
        if v["identityId"] == acct["identityId"]:
            v["session"] = sess
    json.dump(accounts, open(ACC, "w"), indent=1)
    os.chmod(ACC, 0o600)
    c.access_token = sess["accessToken"]
    return c, data.get("userCode")


def main():
    accounts = json.load(open(ACC))
    for key in sorted(accounts):
        acct = accounts[key]
        print(f"\n=== {key} (identity {acct['identityId'][:16]}…) ===", flush=True)
        c, _ = session_for(acct)
        if not c:
            continue
        show("mining", c.call("GET", "/mining/tasks/status"))
        show("overview", c.call("GET", "/overview/users/me/standard"))
        show("inviter-echo", c.call("POST", "/users/me/inviter",
                                    body={"inviterCode": "f34UvL"}))


if __name__ == "__main__":
    main()
