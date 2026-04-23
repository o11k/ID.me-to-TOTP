#!/usr/bin/env python3
"""
Perform the ID.me Authenticator generator-link handshake and print the otpauth:// URI.

Usage:  ./handshake.py 'https://account.id.me/mobile/generator/<token>/<code>'

Deps:   requests, cryptography
"""

import base64
import re
import sys
import uuid

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

API = "https://api.id.me"


def fetch_otpauth(generator_url: str) -> str:
    m = re.search(r"/mobile/generator/([^/]+)/([^/?#]+)", generator_url)
    if not m:
        raise ValueError(f"not a /mobile/generator/<token>/<code> URL: {generator_url}")
    token, code = m.group(1), m.group(2)

    android_id = uuid.uuid4().hex[:16]
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Accept-Language": "en",
        "User-Agent": "me.id.auth/1.12.0-2025082916/2025082916 (Android 14/API 34; Pixel 7/Google)",
        "Firebase-Installation-ID": "",
        "X-Device-UUID": android_id,
        "X-Device-Name": "AUTHN",
    })

    device = {
        "name": "AUTHN",
        "model": "Pixel 7",
        "revision": "1.12.0-2025082916",
        "platform": "Android",
        "version": "34",
        "uuid": android_id,
    }

    # 1. Register device (server side-effect; response only has version gate info)
    s.post(f"{API}/api/mobile/v3/devices/register",
           json={"token": None, **device}).raise_for_status()

    # 2. Ephemeral RSA-2048 keypair. The app sends PEM text re-encoded as base64.
    pub_pem = rsa.generate_private_key(65537, 2048).public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    public_key_b64 = base64.b64encode(pub_pem).decode()

    # 3. Activate — binds token+code to this device, returns the device uuid.
    r = s.post(f"{API}/api/mobile/v3/devices/activate",
               json={"token": token, "code": code, "public_key": public_key_b64})
    r.raise_for_status()
    device_uuid = r.json()["uuid"]

    s.headers["X-Device-User"] = device_uuid

    # 4. Bootstrap events — server returns the queued "generator" registration event.
    r = s.post(f"{API}/api/mobile/v3/events", json={"handles": []})
    r.raise_for_status()
    events = r.json().get("registration") or []
    gen = next((e for e in events if e.get("type") == "generator"), None)
    if gen is None:
        raise RuntimeError(f"no generator event pending: {r.text}")

    # 5. Finalize — server returns the full otpauth:// URI with the TOTP secret.
    r = s.post(f"{API}/api/mobile/v3/events/generator/{gen['uuid']}/registrations",
               json={"token": token, "code": code})
    r.raise_for_status()
    return r.json()["qr_code"]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <https://account.id.me/mobile/generator/TOKEN/CODE>")
    print(fetch_otpauth(sys.argv[1]))
