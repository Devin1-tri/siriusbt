#!/usr/bin/env python3
"""Refresh the stored session, probe the invite/mining endpoints, bind a code, start mining.

Usage: python3 next_steps.py [INVITER_CODE]
"""
import json
import os
import sys
import time

import sirius_api as S

HERE = os.path.dirname(os.path.abspath(__file__))
ACC = os.path.join(HERE, "accounts.json")
CODE = sys.argv[1] if len(sys.argv) > 1 else "f34UvL"


def show(tag, r):
    body = r.get("body") if isinstance(r, dict) else r
    print(f"[{tag}] status={r.get('_status')} body={json.dumps(body, default=str)[:400]}",
          flush=True)
    return body or {}


def main():
    accounts = json.load(open(ACC))
    key = sorted(accounts)[0] if len(sys.argv) < 3 else sys.argv[2]
    acct = accounts[key]
    sess = acct["session"]
    c = S.Sirius(access_token=sess["accessToken"])

    # 1. refresh (access tokens live 900s); refresh tokens are single-use, so if the
    #    refresh is burned do a full /auth/login — which must be sent WITHOUT an
    #    Authorization header (the app strips it before login)
    r = c.call("POST", "/auth/refresh", body={"refreshToken": sess["refreshToken"]})
    show("refresh", r)
    data = (r.get("body") or {}).get("data") or {}
    if not data.get("accessToken"):
        print("refresh gagal -> /auth/login", flush=True)
        anon = S.Sirius()   # no Authorization header
        r = anon.call("POST", "/auth/login", body={"identityId": acct["identityId"],
                                                    "installationId": acct["installationId"],
                                                    "platform": acct["platform"]})
        show("login", r)
        data = (r.get("body") or {}).get("data") or {}
    if data.get("accessToken"):
        sess.update(data)
        c.access_token = sess["accessToken"]
        json.dump(accounts, open(ACC, "w"), indent=1)
        os.chmod(ACC, 0o600)
        print("session saved", flush=True)
    else:
        print("!! no session", flush=True)
        return

    # 2. read state
    show("account", c.call("GET", "/auth/account"))
    show("inviter(GET)", c.call("GET", "/users/me/inviter"))
    show("mining status", c.call("GET", "/mining/tasks/status"))
    show("overview", c.call("GET", "/overview/users/me/standard"))

    # 3. bind invite code
    if CODE:
        for body in ({"inviterCode": CODE}, {"code": CODE}):
            r = c.call("POST", "/users/me/inviter", body=body)
            out = show(f"bind {list(body)[0]}={CODE}", r)
            if (r.get("_status") == 200 and (out.get("code") in (200, None))
                    and not out.get("errorCode")):
                break
        show("inviter(AFTER)", c.call("GET", "/users/me/inviter"))

    # 4. start mining
    show("mining start", c.call("POST", "/mining/tasks/start", body={}))
    show("mining status2", c.call("GET", "/mining/tasks/status"))


if __name__ == "__main__":
    main()
