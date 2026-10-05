#!/usr/bin/env python3
"""Try envelope variants against /app/version/check until the server stops saying
COMMON_INVALID_ENVELOPE (100010). Each variant changes exactly one thing."""
import base64, json, os, uuid, sys
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_public_key
sys.path.insert(0, "/home/ubuntu/bot/sirius")
from sirius_api import PEM, b64u, b64u_d  # noqa: E402

PUB = load_pem_public_key(PEM.encode())
S = requests.Session(); S.headers["User-Agent"] = "okhttp/4.12.0"


def build(method="GET", path="/app/version/check", body=None, query="", pad=False,
          aad_raw=False, kid="kex", reqid=None, v=1, hdr_extra=None):
    cek, reply, iv = os.urandom(32), os.urandom(32), os.urandom(12)
    reqid = reqid or b64u(os.urandom(24))
    hdr = {"alg": "RSA-OAEP-256", "enc": "A256GCM", "typ": "newera-request+jwe", "kid": kid}
    if hdr_extra:
        hdr.update(hdr_extra)
    hdr_json = json.dumps(hdr, separators=(",", ":")).encode()
    enc = (base64.urlsafe_b64encode if pad else b64u)
    hdr_seg = enc(hdr_json).decode() if pad else b64u(hdr_json)
    ek = PUB.encrypt(cek, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                                       algorithm=hashes.SHA256(), label=None))
    payload = {"v": v, "requestId": reqid, "method": method, "path": path,
               "query": query, "replyKey": b64u(reply),
               "body": body if body is not None else {}}
    pt = json.dumps(payload, separators=(",", ":")).encode()
    aad = hdr_json if aad_raw else hdr_seg.encode()
    ct = AESGCM(cek).encrypt(iv, pt, aad)
    segs = [hdr_seg, b64u(ek), b64u(iv), b64u(ct[:-16]), b64u(ct[-16:])]
    return ".".join(segs), reply


def try_get(name, **kw):
    tok, reply = build(**kw)
    r = S.get("https://api.siriussrt.com/app/version/check",
              headers={"X-Api-Envelope": tok}, timeout=25)
    print(f"{name:38} -> {r.status_code} {r.text[:130]}")
    return r


try_get("baseline")
try_get("query=None", query=None)
try_get("aad=raw json", aad_raw=True)
try_get("reqid=uuid", reqid=str(uuid.uuid4()))
try_get("kid=kex + xtra nonce", hdr_extra={"nonce": "abc"})
try_get("pad=True", pad=True)
