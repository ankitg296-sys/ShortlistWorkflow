import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12  # 96-bit nonce standard for AES-GCM


def _decode_master_key(master_key_b64: str) -> bytes:
    key = base64.b64decode(master_key_b64)
    if len(key) != 32:
        raise ValueError(
            f"ENCRYPTION_MASTER_KEY must decode to exactly 32 bytes, got {len(key)}"
        )
    return key


def encrypt(plaintext: str, master_key_b64: str) -> str:
    """
    AES-256-GCM encrypt. Returns base64(nonce || ciphertext || tag).
    A fresh random nonce is generated per call, so encrypting the same
    plaintext twice produces different ciphertexts.
    """
    key = _decode_master_key(master_key_b64)
    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(ciphertext_b64: str, master_key_b64: str) -> str:
    """Inverse of encrypt(). Raises cryptography.exceptions.InvalidTag on tampering."""
    key = _decode_master_key(master_key_b64)
    data = base64.b64decode(ciphertext_b64)
    nonce, ct = data[:_NONCE_BYTES], data[_NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ct, None).decode()
