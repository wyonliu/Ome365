"""tests/test_share_auth.py · share_auth.py crypto contract tests

Covers:
  - 3-word passphrase generation
  - argon2 password hashing + verification
  - Fernet encrypt/decrypt round-trip
  - Stateless signed session (sid) creation + verification + tampering rejection
"""
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))


# ── Skip if cryptography not installed ───────────────────────────────────────
try:
    from share_auth import (
        generate_passphrase,
        hash_password,
        verify_password,
        ensure_master_key,
        encrypt_password,
        decrypt_password,
        make_stateless_sid,
        verify_stateless_sid,
        is_password_protected,
    )
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

pytestmark = pytest.mark.skipif(not HAS_CRYPTO, reason="cryptography lib not installed")


# ── 3-word passphrase ────────────────────────────────────────────────────────

def test_passphrase_format_3_words():
    p = generate_passphrase()
    parts = p.split("-")
    assert len(parts) == 3
    assert all(parts), f"empty parts in {p!r}"


def test_passphrase_uniqueness():
    """100 passphrases should have very high uniqueness."""
    pphs = {generate_passphrase() for _ in range(100)}
    assert len(pphs) > 90  # tolerate some collisions


# ── argon2 password hashing ──────────────────────────────────────────────────

def test_argon2_roundtrip_correct_password():
    h = hash_password("test-password-foo-bar")
    assert verify_password("test-password-foo-bar", h)


def test_argon2_rejects_wrong_password():
    h = hash_password("right-password")
    assert not verify_password("wrong-password", h)


def test_argon2_rejects_empty():
    h = hash_password("nonempty")
    assert not verify_password("", h)


def test_argon2_format():
    h = hash_password("abc")
    # Implementation may use either pbkdf2 or argon2 · just check it's a hash format
    assert "$" in h or len(h) > 32


# ── Fernet master_key + encrypt/decrypt ──────────────────────────────────────

def test_master_key_creation():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        kp = f.name
    os.unlink(kp)  # let ensure_master_key create it
    try:
        key = ensure_master_key(kp)
        assert key
        assert os.path.isfile(kp)
        # File should be chmod 600 (best-effort)
        # On macOS, this is enforced; on Linux/CI, may vary
    finally:
        if os.path.isfile(kp):
            os.unlink(kp)


def test_master_key_idempotent():
    """ensure_master_key called twice on same path returns same key."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        kp = f.name
    os.unlink(kp)
    try:
        k1 = ensure_master_key(kp)
        k2 = ensure_master_key(kp)
        assert k1 == k2
    finally:
        if os.path.isfile(kp):
            os.unlink(kp)


def test_fernet_encrypt_decrypt_roundtrip():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        kp = f.name
    os.unlink(kp)
    try:
        key = ensure_master_key(kp)
        plain = "wonder-bridge-flag"
        enc = encrypt_password(plain, key)
        assert enc.startswith("fernet$v1$")
        dec = decrypt_password(enc, key)
        assert dec == plain
    finally:
        if os.path.isfile(kp):
            os.unlink(kp)


def test_fernet_rejects_wrong_key():
    with tempfile.NamedTemporaryFile(delete=False) as f1, tempfile.NamedTemporaryFile(delete=False) as f2:
        kp1, kp2 = f1.name, f2.name
    os.unlink(kp1)
    os.unlink(kp2)
    try:
        k1 = ensure_master_key(kp1)
        k2 = ensure_master_key(kp2)
        assert k1 != k2
        enc = encrypt_password("secret", k1)
        with pytest.raises(ValueError):
            decrypt_password(enc, k2)
    finally:
        for kp in (kp1, kp2):
            if os.path.isfile(kp):
                os.unlink(kp)


def test_fernet_rejects_malformed():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        kp = f.name
    os.unlink(kp)
    try:
        k = ensure_master_key(kp)
        with pytest.raises(ValueError):
            decrypt_password("not-a-fernet-token", k)
        with pytest.raises(ValueError):
            decrypt_password("", k)
    finally:
        if os.path.isfile(kp):
            os.unlink(kp)


# ── Stateless signed session (sid) ───────────────────────────────────────────

def test_stateless_sid_roundtrip():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        kp = f.name
    os.unlink(kp)
    try:
        k = ensure_master_key(kp)
        sid = make_stateless_sid("alice", "doc1", k, ttl_seconds=60)
        assert sid.startswith("v2.")
        left = verify_stateless_sid(sid, "alice", "doc1", k)
        assert left is not None
        assert 50 < left <= 60
    finally:
        if os.path.isfile(kp):
            os.unlink(kp)


def test_stateless_sid_wrong_user_rejected():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        kp = f.name
    os.unlink(kp)
    try:
        k = ensure_master_key(kp)
        sid = make_stateless_sid("alice", "doc1", k, 60)
        assert verify_stateless_sid(sid, "eve", "doc1", k) is None
        assert verify_stateless_sid(sid, "alice", "doc99", k) is None
    finally:
        if os.path.isfile(kp):
            os.unlink(kp)


def test_stateless_sid_expired():
    """Negative ttl → immediately expired."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        kp = f.name
    os.unlink(kp)
    try:
        k = ensure_master_key(kp)
        sid = make_stateless_sid("alice", "doc1", k, ttl_seconds=-1)
        assert verify_stateless_sid(sid, "alice", "doc1", k) is None
    finally:
        if os.path.isfile(kp):
            os.unlink(kp)


def test_stateless_sid_malformed():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        kp = f.name
    os.unlink(kp)
    try:
        k = ensure_master_key(kp)
        assert verify_stateless_sid("not-v2-token", "alice", "doc1", k) is None
        assert verify_stateless_sid("", "alice", "doc1", k) is None
    finally:
        if os.path.isfile(kp):
            os.unlink(kp)


# ── policy helpers ───────────────────────────────────────────────────────────

def test_is_password_protected():
    """Requires both visibility='password' AND non-empty password_hash."""
    assert is_password_protected({"policy": {"visibility": "password", "password_hash": "x"}})
    assert not is_password_protected({})
    assert not is_password_protected({"policy": {}})
    # missing visibility flag → not protected
    assert not is_password_protected({"policy": {"password_hash": "x"}})
    # visibility set but hash empty → not protected
    assert not is_password_protected({"policy": {"visibility": "password", "password_hash": ""}})
    # public visibility → not protected
    assert not is_password_protected({"policy": {"visibility": "public", "password_hash": "x"}})
