#!/usr/bin/env python3
"""Sirius Network (api.siriussrt.com) client — reversed "New-Era" JWE envelope.

Scheme (from com.siriusnetwork.app v1.0.0, class defpackage.vn):
  request  = JWE compact with header {"alg":"RSA-OAEP-256","enc":"A256GCM",
             "typ":"newera-request+jwe","kid":"kex"}, encrypted_key = RSA-OAEP-256(CEK),
             plaintext = {"v":1,"requestId":..,"method":..,"path":..,"query":..,
                          "replyKey":b64u(32B),"body":..}, AAD = b64u(header JSON)
  response = JWE compact with header {"alg":"dir","enc":"A256GCM","typ":"newera-response+jwe"},
             key = replyKey, plaintext = {"v":1,"requestId":..,"status":..,"body":..}
  GET/DELETE -> the token travels in header `kex`
  POST/PUT/PATCH -> the token IS the body with Content-Type: application/jose
"""
import base64
import json
import os
import uuid

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_public_key

BASE = "https://api.siriussrt.com"
PEM = """-----BEGIN PUBLIC KEY-----
MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAxi0JLtTAK/6i5VXt85BG
R9ekx26sJhNSSzR+j6P3AP5Gz8RggSZ4vGrrUkncFc1FFvuBTZOv1oZ0p7cEglAR
m+Fm6zXMxl8zUlL0A3Axu0P4AqFzg4kMjgEgB0AOTOBB5q5JAe10f6w/8nMrMsfv
7/xF3u94GItZNmVsuHGcX+JcN+WaOtTWGQV5QkvSOKHsrUnQYr8ZKmRgoZ8gTF/I
I8nbsj6bm+0z5xLbtcFHht/R6SXXnmQPKd82r8q4kD4s51qNcmMcyfY3l7Ldf0zr
8AnZMxEnXUosl/E8gVqp+6FQ4pIkbKG91OIhi/312qYeV5VtMKTfSJSgd8BZwUlH
MPA346BjDleOron2XIurOy4YFPUPY9X32kqos3FdZ8mIWDZueBcG3U66lb4Aq1lW
7SAMaObQTmyifxfBO5pY6ox6G/KfUFdg2hJJcZDR8wqoHf2OxA2L8X0qhJOHlL2p
/1heJVbPPLEbkDgTlYJbDMcVXmytta7ZY8nLy1pR8OVxAgMBAAE=
-----END PUBLIC KEY-----"""
PUB = load_pem_public_key(PEM.encode())


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def envelope(method: str, path: str, body=None, query="", request_id=None, token_id=None):
    """Return (jwe_token, reply_key, request_id)."""
    cek = os.urandom(32)                       # content encryption key (RSA-wrapped)
    reply = os.urandom(32)                     # replyKey: server encrypts the response with it
    token_id = token_id or b64u(os.urandom(24))
    iv = os.urandom(12)
    request_id = request_id or b64u(os.urandom(24))   # app uses b64url(24 random bytes)
    hdr_json = json.dumps({"alg": "RSA-OAEP-256", "enc": "A256GCM",
                           "typ": "newera-request+jwe", "kid": "kex"},
                          separators=(",", ":")).encode()
    hdr_b64 = b64u(hdr_json)
    ek = PUB.encrypt(cek, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                                       algorithm=hashes.SHA256(), label=None))
    payload = {"v": 1, "requestId": request_id, "method": method, "path": path,
               "query": query or "", "replyKey": b64u(reply),
               "body": body}          # None -> null. "body":{} is rejected as INVALID_ENVELOPE.
    pt = json.dumps(payload, separators=(",", ":")).encode()
    ct = AESGCM(cek).encrypt(iv, pt, hdr_b64.encode())      # AAD = b64url(header)
    token = ".".join([hdr_b64, b64u(ek), b64u(iv), b64u(ct[:-16]), b64u(ct[-16:])])
    return token, reply, request_id, token_id


def open_response(text: str, reply_key: bytes):
    parts = text.strip().split(".")
    if len(parts) == 5 and parts[1]:            # hdr.ek.iv.ct.tag
        iv_b64, ct_b64, tag_b64 = parts[2], parts[3], parts[4]
    elif len(parts) == 4:                       # hdr..iv.ct+tag  (alg=dir -> empty ek slot)
        iv_b64, ct_b64, tag_b64 = parts[2], parts[3][:-22], parts[3][-22:]
    elif len(parts) == 5:                       # hdr..iv.ct.tag
        iv_b64, ct_b64, tag_b64 = parts[2], parts[3], parts[4]
    else:
        return {"_plain": True, "raw": text}
    hdr = json.loads(b64u_d(parts[0]))
    pt = AESGCM(reply_key).decrypt(b64u_d(iv_b64), b64u_d(ct_b64) + b64u_d(tag_b64),
                                   parts[0].encode())
    out = json.loads(pt)
    out["_hdr"] = hdr
    return out


class Sirius:
    def __init__(self, access_token=None, token_id=None, device=None):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "okhttp/4.12.0"
        self.access_token = access_token
        self.token_id = token_id or b64u(os.urandom(24))
        self.device = device or {}

    def call(self, method: str, path: str, body=None, query=None, raw=False, extra=None):
        token, reply, rid, self.token_id = envelope(method, path, body, query,
                                                    token_id=self.token_id)
        headers = dict(extra or {})          # e.g. {"X-Turnstile-Token": tok}
        if self.access_token:
            headers["Authorization"] = "Bearer " + self.access_token
        if method.upper() in ("GET", "HEAD", "DELETE"):
            headers["X-Api-Envelope"] = token
            r = self.s.request(method, BASE + path, headers=headers, params=query, timeout=30)
        else:
            headers["Content-Type"] = "application/jose"
            headers["Idempotency-Key"] = str(uuid.uuid4())
            r = self.s.request(method, BASE + path, headers=headers, data=token, timeout=30)
        if raw:
            return r
        try:
            return {"_status": r.status_code, **open_response(r.text, reply)}
        except Exception as e:  # noqa: BLE001
            return {"_status": r.status_code, "_decrypt_error": type(e).__name__,
                    "_raw": r.text[:300]}


if __name__ == "__main__":
    c = Sirius()
    print("version/check:", json.dumps(c.call("GET", "/app/version/check"), indent=1)[:600])
    print("registration-config:", json.dumps(c.call("GET", "/auth/registration-config"), indent=1)[:600])
