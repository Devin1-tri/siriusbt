#!/usr/bin/env python3
"""Shared session/state helper for the Sirius bot.

Why this exists (learned the hard way):
  * access tokens live 900 s, refresh tokens are SINGLE-USE -> whoever rotates must
    write the new pair back immediately, or the next rotation answers
    `AUTH_REFRESH_REUSED` and the session dies.
  * `/auth/login` must go out WITHOUT an `Authorization` header (the app strips it);
    sending a stale Bearer makes the server answer `AUTH_TOKEN_INVALID`.
  * two processes (screen dashboard + cron keeper) may refresh at the same time, so
    every read-modify-write of accounts.json happens under one flock held across the
    HTTP call too -- the same footgun that bit UORM.

Usage:
    from sirius_session import accounts_lock, session_for
    with accounts_lock() as accounts:
        client, key = session_for(accounts, key=None)   # rotates + persists inside
"""
import contextlib
import fcntl
import json
import os
import tempfile

import sirius_api as S

HERE = os.path.dirname(os.path.abspath(__file__))
ACC = os.path.join(HERE, "accounts.json")
LOCK = os.path.join(HERE, ".accounts.lock")


def _persist(accounts):
    fd, tmp = tempfile.mkstemp(dir=HERE, prefix=".accounts.")
    with os.fdopen(fd, "w") as fh:
        json.dump(accounts, fh, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, ACC)
    os.chmod(ACC, 0o600)


@contextlib.contextmanager
def accounts_lock(persist=True):
    """Exclusive lock over accounts.json; read inside, write back on success."""
    os.makedirs(HERE, exist_ok=True)
    with open(LOCK, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            accounts = json.load(open(ACC)) if os.path.exists(ACC) else {}
            yield accounts
            if persist:
                _persist(accounts)
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _exchange(kind, body):
    """POST /auth/refresh or /auth/login -> data dict ({} on failure)."""
    c = S.Sirius()          # anonymous: no Authorization header on purpose
    r = c.call("POST", f"/auth/{kind}", body=body)
    data = (r.get("body") or {}).get("data") or {}
    return data if data.get("accessToken") else {}, r


def session_for(accts, key=None):
    """Return (client, key) with a live access token for one account.

    Caller must hold accounts_lock(). Rotated tokens are written into the dict the
    caller owns; the lock holder persists them.
    """
    key = key or sorted(accts)[0]
    acct = accts[key]
    sess = acct["session"]

    data, r = _exchange("refresh", {"refreshToken": sess["refreshToken"]})
    if not data.get("accessToken"):
        data, r = _exchange("login", {"identityId": acct["identityId"],
                                      "installationId": acct["installationId"],
                                      "platform": acct["platform"]})
    if not data.get("accessToken"):
        return None, key
    sess.update(data)
    acct["session"] = sess
    accts[key] = acct
    client = S.Sirius(access_token=sess["accessToken"])
    return client, key


def client_for_all(accts):
    """[(key, client), ...] for every account, one refresh/login each."""
    out = []
    for key in sorted(accts):
        c, k = session_for(accts, key)
        out.append((k, c))
    return out
