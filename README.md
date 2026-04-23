# ID.me to TOTP

Extract the TOTP secret from an ID.me Authenticator "Code Generator" enrollment link, so you can import it into any authenticator app (Aegis, 1Password, Bitwarden, Authy, Google Authenticator, a hardware key, etc.) instead of being locked into the ID.me mobile app.

The ID.me Authenticator app doesn't let you view or export your TOTP secret. This script performs the same handshake the app does when you scan the enrollment QR code, and prints the resulting `otpauth://` URI — which contains the base32 secret.

## Usage

When you're setting up a new Code Generator on [account.id.me](https://account.id.me), it shows you a QR code. Instead of scanning it with the ID.me app, decode the QR to get the URL — it will look like:

```
https://account.id.me/mobile/generator/<token>/<code>
```

Then:

```bash
pip install requests cryptography
python3 handshake.py 'https://account.id.me/mobile/generator/<token>/<code>'
```

Output:

```
otpauth://totp/ID.me:you%40example.com?secret=BASE32SECRETHERE&issuer=ID.me
```

Paste that URI into your authenticator of choice (most accept `otpauth://` URIs directly, or you can generate a QR from it with `qrencode`).

## Notes

- The enrollment link is **single-use**. Once this script (or the ID.me app) has consumed it, the server won't accept it again.
- You can also decode the QR without scanning it on your phone — `zbarimg qrcode.png` works on a screenshot from your browser.
- No ID.me account credentials are involved. The `token`/`code` pair in the URL is its own short-lived authorization.

## How it works

Four POSTs to `https://api.id.me`:

1. `POST /api/mobile/v3/devices/register` — identifies the "device" (noise, but the app does it)
2. `POST /api/mobile/v3/devices/activate` with `{token, code, public_key}` — binds the enrollment to an ephemeral RSA-2048 keypair, returns a `deviceUuid`
3. `POST /api/mobile/v3/events` — fetches the pending "generator" registration event and its `eventUuid`
4. `POST /api/mobile/v3/events/generator/<eventUuid>/registrations` with `{token, code}` — the server responds with `{qr_code: "otpauth://totp/...?secret=..."}`

The `public_key` is an ephemeral RSA key used only for this activation (the app calls it `RSA_TEMPORAL_KEY`); it's not used to protect the TOTP secret, which arrives in plaintext over TLS.

Reverse-engineered from a decompile of the ID.me Authenticator Android app (`me.id.auth`, version 1.12.0), with the help of Claude Opus 4.7.
