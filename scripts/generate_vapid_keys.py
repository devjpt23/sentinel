#!/usr/bin/env python
"""Generate VAPID keys for web push notifications. Run once, add to env vars."""

try:
    from py_vapid import Vapid
except ImportError:
    print("py-vapid not installed. Run: pip install py-vapid")
    raise SystemExit(1)

v = Vapid()
v.generate_keys()

# Newer py-vapid versions return EC key objects, not strings.
# Convert to the Base64 URL-encoded format the push protocol expects.
import base64

def _ec_public_key_to_bytes(key):
    """Extract the raw public key bytes in uncompressed point format."""
    numbers = key.public_numbers()
    x = numbers.x.to_bytes(32, byteorder='big')
    y = numbers.y.to_bytes(32, byteorder='big')
    return b'\x04' + x + y  # Uncompressed point prefix

def _ec_private_key_to_pem(key):
    """Serialize private key as PEM."""
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption,
    )
    return key.private_bytes(
        Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
    ).decode()

pub_bytes = _ec_public_key_to_bytes(v.public_key)
pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b'=').decode()
priv_pem = _ec_private_key_to_pem(v.private_key)

print("VAPID_PUBLIC_KEY (for Vercel, NEXT_PUBLIC_VAPID_PUBLIC_KEY):")
print(f"  {pub_b64}")
print()
print("VAPID_PRIVATE_KEY (for VPS, PEM format):")
print(priv_pem)
print()
print("Add to your VPS environment variables:")
print(f"  export VAPID_PUBLIC_KEY='{pub_b64}'")
print(f"  export VAPID_PRIVATE_KEY='{priv_pem.strip()}'")
print()
print("Add to your Vercel project environment variables:")
print(f"  NEXT_PUBLIC_VAPID_PUBLIC_KEY={pub_b64}")
print()
print("WARNING: Never change these keys after deployment. All existing subscriptions will break.")
