"""Token encryption + secret-access audit trail."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import get_settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored credential") from exc


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "••••"
    return f"{secret[:4]}…{secret[-4:]}"


def reveal_repo_token(
    db: Session,
    *,
    repository_id: str,
    token_encrypted: str,
    purpose: str,
    actor: str = "system",
) -> str:
    """Decrypt a repo token and append an audit log row (never log the secret)."""
    from app.models import SecretAccessLog

    token = decrypt_secret(token_encrypted) if token_encrypted else ""
    db.add(
        SecretAccessLog(
            repository_id=repository_id,
            purpose=purpose,
            actor=actor,
        )
    )
    db.commit()
    return token
