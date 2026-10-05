# siriusbt

Automation bot for **SiriusNetwork** (SRT / `siriussrt.com`, Android app
`com.siriusnetwork.app`): registers identities straight against the app's
backend, binds an invite code, and keeps a 24-hour mining round running —
no emulator, no phone, no manual taps.

```
SIRIUS NETWORK BOT  ·  api.siriussrt.com  ·  round 24h, settle tiap 60 mnt
==============================================================================
akun           kode    mining    round s/d     reward    balance  inv   refs
------------------------------------------------------------------------------
4df0998efab3   DmBYfE  RUNNING   10-06 06:40   0.0000    0.0000   yes   0
7bb643d631de   3hd3Qy  RUNNING   10-06 06:44   0.0000    0.0000   yes   0
```

* rate **0.0069 SST/min ≈ 0.4166 SST per settlement ≈ 10 SST/akun/hari**
* rounds last 24 h, the balance moves at each 60-minute settlement
* invite code is enforced on every pass (idempotent `POST /users/me/inviter`)

---

## How the bot talks to the backend

Everything is plain HTTP against `https://api.siriussrt.com`, but every call
travels inside a **JWE envelope** the app itself uses (`newera-request+jwe`):

| | |
|---|---|
| request | JWE compact, `alg=RSA-OAEP-256`, `enc=A256GCM`, `kid=kex`, AAD = b64url(header) |
| plaintext | `{"v":1,"requestId","method","path","query","replyKey","body"}` — **`"body":null` for bodyless calls** (`"body":{}` → `100010 INVALID_ENVELOPE`) |
| CEK | 32 random bytes RSA-OAEP-256 wrapped with the public key shipped inside the APK |
| response | 4-segment JWE (`hdr..iv.ct+tag`), `alg=dir`, decrypted with our `replyKey` |
| transport | GET/DELETE → `X-Api-Envelope` header · POST/PUT/PATCH → the token **is** the body, `Content-Type: application/jose` |

`sirius_api.py` is the whole client (~130 lines).

### Session rules that will bite you

* access token **900 s**; refresh token is **single-use** → rotating twice answers
  `AUTH_REFRESH_REUSED` and kills the session. Every rotation therefore happens
  under `flock` on `.accounts.lock`, held across the HTTP call
  (`sirius_session.accounts_lock`), and is written back atomically.
* recovery is `POST /auth/login {identityId, installationId, platform}` with a
  **flat body and no `Authorization` header** (the app strips it; a stale Bearer
  makes the server answer `AUTH_TOKEN_INVALID` instead of logging in).

---

## Files

| file | role |
|---|---|
| `sirius_api.py` | JWE envelope client (request + response) |
| `sirius_session.py` | flock'd accounts.json + refresh/login rotation |
| `sirius_dashboard.py` | live dashboard + keep-alive loop (30 min, `INTERVAL_MIN`) |
| `mine_daily.py` | one keeper pass: bind invite + start round if missing |
| `new_account.py` | full registration pipeline for a new account |
| `solve_ts.py` + `turnstile/` | Cloudflare Turnstile solver for `/auth/register` |
| `sirius.sh` | control script (`start`/`once`/`status`/`new`/`ensure`/`logs`) |
| `probe_*.py`, `register.py`, `next_steps.py`, `status.py` | the reverse-engineering + QA probes kept for reference |

`accounts.json` (identities + tokens) is **git-ignored** and chmod 600.

---

## Quickstart

```bash
# 1. deps (the API side needs `cryptography`, the solver needs camoufox)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. two local services the Turnstile solver needs
./sirius.sh ensure          # http :8002 (widget page) + WARP SOCKS :25344

# 3. run
./sirius.sh status          # one snapshot
./sirius.sh start           # live dashboard + keep-alive (Ctrl+C stops)
./sirius.sh new f34UvL      # register another identity, bind invite, start mining
```

Optional environment: `SIRIUS_INVITE` (invite code, default `f34UvL`),
`INTERVAL_MIN` (dashboard loop, default `30`).

### Runner: screen + cron fallback

```bash
screen -dmS sirius bash
screen -S sirius -X stuff 'cd /home/ubuntu/bot/sirius && ./sirius.sh start\n'
screen -r sirius            # attach; Ctrl+C stops the loop but keeps the session
```

A silent cron tick (`sirius_mine.sh`, every 6 h) re-runs the keeper as a safety
net: it prints nothing while every round is RUNNING, and only pings when it had
to start a round or something failed.

---

## Why no emulator

The APK (`com.siriusnetwork.app`, Kotlin Multiplatform + PairIP) turned out to be
a thin shell over the API: registration, invite binding and mining start are four
POSTs. The emulator route wasn't even possible on this box (no `/dev/kvm`), which
is what forced the reverse — and the reverse is the durable part.

**Registration** needs a Turnstile token: the sitekey refuses `localhost`, so the
same widget page is served locally and Firefox is told to resolve
`api.siriussrt.com` → `127.0.0.1` (`network.dns.localDomains`), with the
challenge egressing through WARP. Solve takes 10–250 s; the token is single-use
with a ~5 min TTL, so `new_account.py` chains solve → register in one call.

## License

MIT — see [LICENSE](LICENSE). Zero credentials in this repo; if you fork it,
bring your own identities.
