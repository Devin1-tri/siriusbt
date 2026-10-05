#!/usr/bin/env python3
"""Untried angles on the New-Era envelope (everything before probed: hash pairs, both keys,
segment order, base64 padding, transport). New here:
  1. OAEP label variants (RFC says empty; some JVM stacks pass something else)
  2. AAD variants (we assume b64(header); maybe the server uses the raw header JSON / none)
  3. payload shape variants (v as string, query absent, body null, ...)
  4. a decrypt oracle: is the CEK unwrap succeeding? -> wrap-valid+tag-broken vs random ek,
     compared by response text AND by timing (a 3072-bit private op costs a few ms).
"""
import json
import os
import statistics
import time

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import sirius_api as S

PATH = "/app/version/check"
HDR = {"alg": "RSA-OAEP-256", "enc": "A256GCM", "typ": "newera-request+jwe", "kid": "kex"}
HDR_JSON = json.dumps(HDR, separators=(",", ":")).encode()
HB = S.b64u(HDR_JSON)

s = requests.Session()
s.headers["User-Agent"] = "okhttp/4.12.0"


def build(*, label=None, aad=None, payload=None, break_tag=False, random_ek=False, method="GET"):
    cek, reply, iv = os.urandom(32), os.urandom(32), os.urandom(12)
    ek = os.urandom(384) if random_ek else S.PUB.encrypt(
        cek, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                          algorithm=hashes.SHA256(), label=label))
    rid = S.b64u(os.urandom(24))
    pl = payload if payload is not None else {
        "v": 1, "requestId": rid, "method": method, "path": PATH, "query": "",
        "replyKey": S.b64u(reply), "body": {}}
    pt = json.dumps(pl, separators=(",", ":")).encode()
    a = HB.encode() if aad is None else aad
    ct = AESGCM(cek).encrypt(iv, pt, a)
    body_ct, tag = ct[:-16], ct[-16:]
    if break_tag:
        tag = bytes([tag[0] ^ 0xFF]) + tag[1:]
    return ".".join([HB, S.b64u(ek), S.b64u(iv), S.b64u(body_ct), S.b64u(tag)]), reply, rid


def send(token, method="GET", header="X-Api-Envelope"):
    if method in ("GET", "DELETE"):
        return s.request(method, S.BASE + PATH, headers={header: token}, timeout=30)
    return s.request(method, S.BASE + PATH,
                     headers={"Content-Type": "application/jose"}, data=token, timeout=30)


def show(tag, r):
    print(f"  {tag:44} -> {r.status_code} {r.text[:110]}")


print("=== 0. baseline (klien apa adanya) ===")
show("klien sirius_api.Sirius().call", S.Sirius().call("GET", PATH, raw=True))

print("\n=== 1. varian label OAEP ===")
for nm, lab in [("empty", None), ("typ", b"newera-request+jwe"), ("kid", b"kex"),
                ("header-json", HDR_JSON), ("header-b64", HB.encode())]:
    t, _, _ = build(label=lab)
    show(f"label={nm}", send(t))

print("\n=== 2. varian AAD ===")
for nm, a in [("b64(header) [skrg]", HB.encode()), ("header-json mentah", HDR_JSON),
              ("tanpa AAD", b""), ("header-json+padding", S.b64u(HDR_JSON).encode())]:
    t, _, _ = build(aad=a)
    show(f"aad={nm}", send(t))

print("\n=== 3. varian bentuk payload ===")
rid0 = S.b64u(os.urandom(24))
variants = {
    "v string": {"v": "1", "requestId": rid0, "method": "GET", "path": PATH, "query": "",
                 "replyKey": S.b64u(os.urandom(32)), "body": {}},
    "tanpa query": {"v": 1, "requestId": rid0, "method": "GET", "path": PATH,
                    "replyKey": S.b64u(os.urandom(32)), "body": {}},
    "body null": {"v": 1, "requestId": rid0, "method": "GET", "path": PATH, "query": "",
                  "replyKey": S.b64u(os.urandom(32)), "body": None},
    "path+query gabung": {"v": 1, "requestId": rid0, "method": "GET", "path": PATH + "?",
                          "query": "", "replyKey": S.b64u(os.urandom(32)), "body": {}},
}
for nm, pl in variants.items():
    t, _, _ = build(payload=pl)
    show(f"payload={nm}", send(t))

print("\n=== 4. nama header alternatif ===")
for h in ("X-Api-Envelope", "x-api-envelope", "Kex", "X-Api-Kex", "Envelope"):
    t, _, _ = build()
    show(f"header={h}", send(t, header=h))

print("\n=== 5. ORACLE: apakah CEK kebuka? (teks + waktu) ===")
cases = {"wrap-valid + tag-rusak": dict(break_tag=True), "ek acak 384B": dict(random_ek=True)}
for nm, kw in cases.items():
    texts = set()
    ts = []
    for _ in range(12):
        t, _, _ = build(**kw)
        t0 = time.perf_counter()
        r = send(t)
        ts.append((time.perf_counter() - t0) * 1000)
        texts.add(r.text[:80])
    print(f"  {nm:26} median={statistics.median(ts):7.1f} ms  min={min(ts):6.1f} ms  "
          f"balasan-unik={texts}")
