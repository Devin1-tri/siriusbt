#!/usr/bin/env python3
"""Sirius Network bot -- live dashboard + keep-alive loop.

One pass per account: ensure invite code is bound, ensure a mining round is
running, then print a status line. Loops every INTERVAL_MIN (default 30) until
Ctrl+C, which is what the `screen sirius` panel runs (`./sirius.sh start`).

Server timestamps are UTC; they are rendered in the box's local time.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

from sirius_session import accounts_lock, session_for

INTERVAL_MIN = float(os.environ.get("INTERVAL_MIN", "30"))
INVITE = os.environ.get("SIRIUS_INVITE", "f34UvL")


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def local(ts):
    """'2026-10-05T22:40:25.367719' (UTC) -> '06:40' local, or '-'."""
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%m-%d %H:%M")
    except Exception:
        return str(ts)[:16]


def one_pass():
    rows = []
    with accounts_lock() as accts:
        for key in sorted(accts):
            acct = accts[key]
            client, key = session_for(accts, key)
            if not client:
                rows.append((key, "-", "AUTH-ERROR", "-", "-", "-", "-", "-"))
                continue

            # enforce the invite binding (idempotent: returns invitationBound)
            inv = (client.call("POST", "/users/me/inviter",
                               body={"inviterCode": INVITE}).get("body") or {}).get("data") or {}
            st = (client.call("GET", "/mining/tasks/status").get("body") or {}).get("data") or {}
            if st.get("miningStatus") != "RUNNING":
                started = (client.call("POST", "/mining/tasks/start",
                                       body={}).get("body") or {}).get("data") or {}
                st = (client.call("GET", "/mining/tasks/status").get("body") or {}).get("data") or {}
                if not started.get("roundId"):
                    rows.append((key, acct["session"].get("userCode", "?"),
                                 "START-FAIL", "-", "-", "-", "-", "-"))
                    continue
            ov = (client.call("GET", "/overview/users/me/standard").get("body") or {}).get("data") or {}

            rows.append((
                key,
                acct["session"].get("userCode", "?"),
                st.get("miningStatus", "?"),
                local(st.get("largeCycleEndsAt")),
                st.get("totalMiningReward", "0"),
                (ov.get("points") or {}).get("totalBalance", "0"),
                "yes" if inv.get("invitationBound") else "no",
                str((ov.get("referral") or {}).get("directReferralCount", 0)),
            ))
    return rows


def render(rows, n):
    os.system("clear" if os.environ.get("TERM") else "true")
    print("=" * 78)
    print("  SIRIUS NETWORK BOT  ·  api.siriussrt.com  ·  round 24h, settle tiap 60 mnt")
    print(f"  pass #{n} @ {time.strftime('%Y-%m-%d %H:%M:%S')}  ·  interval {INTERVAL_MIN}m"
          f"  ·  invite {INVITE}")
    print("=" * 78)
    print(f"{'akun':<14}{'kode':<9}{'mining':<10}{'round s/d':<15}"
          f"{'reward':<10}{'balance':<10}{'inv':<5}{'refs'}")
    print("-" * 78)
    for r in rows:
        print(f"{r[0]:<14}{r[1]:<9}{r[2]:<10}{r[3]:<15}{r[4]:<10}{r[5]:<10}{r[6]:<5}{r[7]}")
    print("-" * 78)
    print("rate 0.0069 SST/menit = ~10 SST/akun/hari · Ctrl+C keluar, ./sirius.sh start lagi")
    print(f"next pass dalam {INTERVAL_MIN:.0f} menit", flush=True)


def main():
    n = 0
    once = "--once" in sys.argv
    while True:
        n += 1
        try:
            render(one_pass(), n)
        except KeyboardInterrupt:
            raise
        except Exception as exc:                      # noqa: BLE001
            log("PASS ERROR:", type(exc).__name__, exc)
        if once:
            return
        try:
            time.sleep(INTERVAL_MIN * 60)
        except KeyboardInterrupt:
            raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[stopped]", flush=True)
