#!/usr/bin/env python3
"""Wide variant matrix for the Sirius envelope — print the error for each combo."""
import base64, json, os, sys
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_public_key
sys.path.insert(0, "/home/ubuntu/bot/sirius")
from sirius_api import PEM, b64u  # noqa: E402

PUB = load_pem_public_key(PEM.encode())
PAIRIP = None
S = requests.Session(); S.headers["User-Agent"] = "okhttp/5.3.2"
URL = "https://api.siriussrt.com/app/version/check"


def mk(method="GET", path="/app/version/check", query="", body=None, v=1, alg_hdr="RSA-OAEP-256",
       kid="kex", rsa_sha=hashes.SHA256(), aad_mode="b64", transport="header", pad=False,
       cek_len=32, extra_hdr=None, reqid=None):
    cek, reply, iv = os.urandom(cek_len), os.urandom(32), os.urandom(12)
    reqid = reqid or b64u(os.urandom(24))
    hdr = {"alg": alg_hdr, "enc": "A256GCM", "typ": "newera-request+jwe"}
    if kid is not None:
        hdr["kid"] = kid
    if extra_hdr:
        hdr.update(extra_hdr)
    hdr_json = json.dumps(hdr, separators=(",", ":")).encode()
    hdr_seg = base64.urlsafe_b64encode(hdr_json).decode() if pad else b64u(hdr_json)
    # RSA wrap
    if alg_hdr.startswith("RSA-OAEP"):
        ek = PUB.encrypt(cek, padding.OAEP(mgf=padding.MGF1(rsa_sha), algorithm=rsa_sha, label=None))
    else:
        ek = PUB.encrypt(cek, padding.PKCS1v15())
    payload = {"v": v, "requestId": reqid, "method": method, "path": path, "query": query,
               "replyKey": b64u(reply), "body": body if body is not None else {}}
    pt = json.dumps(payload, separators=(",", ":")).encode()
    aad = {"b64": hdr_seg.encode(), "raw": hdr_json, "none": None}[aad_mode]
    ct = AESGCM(cek).encrypt(iv, pt, aad)
    tok = ".".join([hdr_seg, b64u(ek), b64u(iv), b64u(ct[:-16]), b64u(ct[-16:])])
    if transport == "header":
        r = S.get(URL, headers={"X-Api-Envelope": tok}, timeout=20)
    elif transport == "body":
        r = S.post(URL, data=tok, headers={"Content-Type": "application/jose"}, timeout=20)
    else:
        r = S.post(URL, data=tok, headers={"Content-Type": "application/jose", "X-Api-Envelope": tok}, timeout=20)
    return r


cases = {
    "baseline": {},
    "v=2": {"v": 2},
    "no kid": {"kid": None},
    "alg RSA-OAEP(sha1)": {"alg_hdr": "RSA-OAEP"},
    "alg PKCS1v15": {"alg_hdr": "RSA1_5"},
    "aad=None": {"aad_mode": "none"},
    "transport=body": {"transport": "body"},
    "transport=both": {"transport": "both"},
    "reqid hex32": {"reqid": os.urandom(16).hex()},
    "query=null": {"query": None},
    "hdr cty+jti": {"extra_hdr": {"cty": "json", "jti": b64u(os.urandom(24))}},
    "body=null": {"body": None},
}
for name, kw in cases.items():
    try:
        r = mk(**kw)
        print(f"{name:22} {r.status_code} {r.text[:120]}")
    except Exception as e:  # noqa: BLE001
        print(f"{name:22} ERR {type(e).__name__}: {str(e)[:80]}")
print("--- turnstile-test path ---")
for p in ("/turnstile-test/", "/turnstile-test/index.html"):
    r = S.get("https://api.siriussrt.com" + p, timeout=15)
    print(f"{p:26} {r.status_code} {r.text[:120]}")
