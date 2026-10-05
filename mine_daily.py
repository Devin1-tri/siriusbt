#!/usr/bin/env python3
"""Sirius daily mining keeper: for every stored account, make sure a round is running.

A round lasts 24 h (settlement every 60 min) and the balance only moves at
settlement, so this must fire at least daily -- the cron wrapper `sirius_mine.sh`
runs it every 6 h and stays silent while everything is already RUNNING.

Safe to run next to the screen dashboard: every token rotation happens under one
flock held across the HTTP call (sirius_session.accounts_lock), because refresh
tokens are single-use and a double rotation kills the session.
"""
import json
import os
import time

from sirius_session import accounts_lock, session_for


def log(*a):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]", *a, flush=True)


def keep_round_running(key, client):
    st = (client.call("GET", "/mining/tasks/status").get("body") or {}).get("data") or {}
    if st.get("miningStatus") == "RUNNING":
        log(key, "RUNNING sampai", st.get("largeCycleEndsAt"),
            "| reward", st.get("totalMiningReward"))
        return True
    r = client.call("POST", "/mining/tasks/start", body={})
    d = (r.get("body") or {}).get("data") or {}
    if d.get("roundId"):
        log(key, "STARTED round", d["roundId"], "->", d.get("endsAt"))
        return True
    log(key, "START GAGAL:", json.dumps(r.get("body"), default=str)[:250])
    return False


def main():
    ok = True
    with accounts_lock() as accts:
        for key in sorted(accts):
            client, key = session_for(accts, key)
            if not client:
                log(key, "AUTH GAGAL")
                ok = False
                continue
            ok = keep_round_running(key, client) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
