"""
AES-256-GCM encryption for API keys and sensitive credentials.
Each key is encrypted independently so a single compromise does not
expose other credentials.
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings
from app.observability.logging_config import get_logger

logger = get_logger(__name__)

_NONCE_SIZE = 12  # 96-bit nonce for AES-GCM


def _get_key() -> bytes:
    """Return the 32-byte AES-256 encryption key from settings."""
    return get_settings().get_encryption_key()


def encrypt_api_key(plaintext: str) -> str:
    """
    Encrypt a plaintext API key using AES-256-GCM.

    Returns a base64url-encoded string: <nonce_b64>.<ciphertext_b64>
    The nonce is randomly generated per encryption call.
    """
    key = _get_key()
    nonce = os.urandom(_NONCE_SIZE)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    encoded = (
        base64.urlsafe_b64encode(nonce).decode()
        + "."
        + base64.urlsafe_b64encode(ciphertext).decode()
    )
    logger.debug("api_key_encrypted", key_length=len(plaintext))
    return encoded


def decrypt_api_key(encrypted: str) -> str:
    """
    Decrypt an AES-256-GCM encrypted API key.

    Expects the format produced by encrypt_api_key().
    Raises ValueError on malformed input or authentication failure.
    """
    try:
        nonce_b64, ciphertext_b64 = encrypted.split(".", 1)
        nonce = base64.urlsafe_b64decode(nonce_b64)
        ciphertext = base64.urlsafe_b64decode(ciphertext_b64)
    except (ValueError, Exception) as exc:
        raise ValueError("Malformed encrypted key format") from exc

    key = _get_key()
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ValueError("Decryption failed — key may be wrong or data corrupted") from exc

    return plaintext.decode("utf-8")
