import base64
import os

import pytest
from cryptography.exceptions import InvalidTag

from processing_service.vault.crypto import decrypt, encrypt


def random_master_key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def test_roundtrip():
    key = random_master_key()
    plaintext = "sk-ant-api-key-abcdef1234567890"
    assert decrypt(encrypt(plaintext, key), key) == plaintext


def test_empty_string_roundtrip():
    key = random_master_key()
    assert decrypt(encrypt("", key), key) == ""


def test_different_nonces_per_call():
    """Same plaintext must produce different ciphertexts (random nonce)."""
    key = random_master_key()
    plaintext = "sk-ant-same-plaintext"
    assert encrypt(plaintext, key) != encrypt(plaintext, key)


def test_wrong_key_raises():
    key1 = random_master_key()
    key2 = random_master_key()
    ct = encrypt("secret", key1)
    with pytest.raises(InvalidTag):
        decrypt(ct, key2)


def test_tampered_ciphertext_raises():
    key = random_master_key()
    ct_b64 = encrypt("secret", key)
    # Flip a byte in the middle of the ciphertext
    ct = bytearray(base64.b64decode(ct_b64))
    ct[len(ct) // 2] ^= 0xFF
    with pytest.raises(InvalidTag):
        decrypt(base64.b64encode(bytes(ct)).decode(), key)


def test_invalid_master_key_length():
    bad_key = base64.b64encode(b"only-16-bytes!!!").decode()  # 16 bytes, not 32
    with pytest.raises(ValueError, match="32 bytes"):
        encrypt("anything", bad_key)
