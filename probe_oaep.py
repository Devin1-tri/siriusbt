#!/usr/bin/env python3
"""RSA-OAEP hash combos: Java's OAEPWithSHA-256AndMGF1Padding defaults to MGF1-SHA1."""
import json, os, sys
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_public_key
sys.path.insert(0, "/home/ubuntu/bot/sirius")
from sirius_api import PEM, b64u  # noqa: E402

PUB = load_pem_public_key(PEM.encode())
S = requests.Session(); S.headers["User-Agent"] = "okhttp/5.3.2"
URL = "https://api.siriussrt.com/app/version/check"


def go(name, alg, digest, mgf):
    cek, reply, iv = os.urandom(32), os.urandom(32), os.urandom(12)
    hdr = {"alg": alg, "enc": "A256GCM", "typ": "newera-request+jwe", "kid": "kex"}
    hdr_json = json.dumps(hdr, separators=(",", ":")).encode()
    hdr_seg = b64u(hdr_json)
    ek = PUB.encrypt(cek, padding.OAEP(mgf=padding.MGF1(mgf), algorithm=digest, label=None))
    payload = {"v": 1, "requestId": b64u(os.urandom(24)), "method": "GET",
               "path": "/app/version/check", "query": "", "replyKey": b64u(reply), "body": {}}
    ct = AESGCM(cek).encrypt(iv, json.dumps(payload, separators=(",", ":")).encode(), hdr_seg.encode())
    tok = ".".join([hdr_seg, b64u(ek), b64u(iv), b64u(ct[:-16]), b64u(ct[-16:])])
    r = S.get(URL, headers={"X-Api-Envelope": tok}, timeout=20)
    print(f"{name:44} {r.status_code} {r.text[:120]}")


go("SHA256 digest + MGF1-SHA1 (Java default)", "RSA-OAEP-256", hashes.SHA256(), hashes.SHA1())
go("SHA256 + MGF1-SHA256", "RSA-OAEP-256", hashes.SHA256(), hashes.SHA256())
go("SHA1 + MGF1-SHA1 (declared 256)", "RSA-OAEP-256", hashes.SHA1(), hashes.SHA1())
go("SHA1 + MGF1-SHA256", "RSA-OAEP-256", hashes.SHA1(), hashes.SHA256())
