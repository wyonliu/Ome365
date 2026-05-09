"""
ome365.signing · v1.1.2 P3 #17 · ed25519 agent-card signing
[decision: 2026-05-09-v1-1-2-final-batch]

Provides real ed25519 signatures for /.well-known/agent-card.json.
- Key file: vault/.ome365/keys/agent-card.ed25519 (gitignored)
- Auto-generates a key on first call · 32 bytes · written 0600
- sign(payload_dict) → returns signed dict with ed25519 signature
- verify(signed) → True if signature matches

Stable: cryptography>=41 (already in requirements.txt).
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional


def _vault_root(vault: Optional[Path] = None) -> Path:
    if vault:
        return Path(vault).resolve()
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


def _key_path(vault: Optional[Path] = None) -> Path:
    return _vault_root(vault) / ".ome365" / "keys" / "agent-card.ed25519"


def _ensure_key(vault: Optional[Path] = None) -> bytes:
    """Load or generate the 32-byte ed25519 private key."""
    fp = _key_path(vault)
    if fp.exists():
        data = fp.read_bytes()
        if len(data) == 32:
            return data
    # Generate fresh
    fp.parent.mkdir(parents=True, exist_ok=True)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    sk = Ed25519PrivateKey.generate()
    raw = sk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    fp.write_bytes(raw)
    try:
        os.chmod(fp, 0o600)
    except Exception:
        pass
    return raw


def public_key_b64(vault: Optional[Path] = None) -> str:
    """Returns the base64-encoded ed25519 public key (32 bytes)."""
    raw = _ensure_key(vault)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    sk = Ed25519PrivateKey.from_private_bytes(raw)
    pk_bytes = sk.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(pk_bytes).decode("ascii")


def sign(payload: dict, *, vault: Optional[Path] = None) -> dict:
    """
    Sign a JSON-serializable dict. Returns the dict with these new fields:
      · signature   = base64(ed25519(canonical_json_bytes))
      · signing_alg = "ed25519"
      · signing_pubkey_b64 = base64(public_key)
    Canonical JSON: sort_keys=True, separators=(",", ":"), ensure_ascii=False.
    """
    raw = _ensure_key(vault)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    sk = Ed25519PrivateKey.from_private_bytes(raw)
    # Build canonical body for signing (exclude any pre-existing signature fields)
    body = {k: v for k, v in payload.items()
            if k not in ("signature", "signing_alg", "signing_pubkey_b64")}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    sig = sk.sign(canonical)
    return {
        **body,
        "signature": base64.b64encode(sig).decode("ascii"),
        "signing_alg": "ed25519",
        "signing_pubkey_b64": public_key_b64(vault),
    }


def verify(signed: dict) -> bool:
    """True if signature matches public key. Returns False on any error."""
    try:
        sig = base64.b64decode(signed["signature"])
        pubkey = base64.b64decode(signed["signing_pubkey_b64"])
    except Exception:
        return False

    body = {k: v for k, v in signed.items()
            if k not in ("signature", "signing_alg", "signing_pubkey_b64")}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pk = Ed25519PublicKey.from_public_bytes(pubkey)
        pk.verify(sig, canonical)
        return True
    except Exception:
        return False


__all__ = ["sign", "verify", "public_key_b64"]
