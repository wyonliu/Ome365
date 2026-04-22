"""
Ome365 · Share password protection (T2)

零新依赖：`hashlib.pbkdf2_hmac` (Python 3.4+ stdlib，所有 OpenSSL/LibreSSL 都支持) + sqlite3。
远端 Python 3.6.8 + fastapi 0.83 约束下直接跑。macOS LibreSSL 没有 scrypt，pbkdf2 通吃。

组成：
  - generate_passphrase()             -> 自动生成三词密码
  - hash_password / verify_password   -> pbkdf2 封装（OWASP 2023 建议 600k 迭代）
  - AuthStore                          -> SQLite：sessions / failed_attempts / audit
  - 三层速率限制：IP×doc / doc/h / doc/day
  - 工具函数 policy_* / cookie_name 等

所有 SQL 写操作走一把全局锁（sqlite3 不是默认线程安全）。

密码 hash 编码（紧凑 ASCII，可直接进 share_registry.json）:
    pbkdf2$sha256,iter=600000$<b64url-salt>$<b64url-hash>
"""
import base64
import hashlib
import hmac as _hmac
import json
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from share_wordlist import WORDS  # type: ignore


# ── pbkdf2 参数 ──────────────────────────────────────────
# OWASP 2023：PBKDF2-HMAC-SHA256 ≥ 600_000 iterations。
# ~300ms/verify on macOS M 系，~500ms 老 Xeon。配合速率限制足够。
_PBKDF2_HASH = "sha256"
_PBKDF2_ITER = 600_000
_PBKDF2_DKLEN = 32


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def hash_password(plain: str) -> str:
    """生成 pbkdf2$... 形式的密码哈希。"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(_PBKDF2_HASH, plain.encode("utf-8"), salt, _PBKDF2_ITER, _PBKDF2_DKLEN)
    return "pbkdf2${},iter={}${}${}".format(
        _PBKDF2_HASH, _PBKDF2_ITER, _b64e(salt), _b64e(dk),
    )


def verify_password(plain: str, encoded: str) -> bool:
    """恒时比较。格式错 / 参数异常 → False。"""
    try:
        parts = encoded.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2":
            return False
        p1 = parts[1].split(",")
        alg = p1[0]
        params = dict(kv.split("=") for kv in p1[1:])
        it = int(params["iter"])
        salt = _b64d(parts[2])
        expected = _b64d(parts[3])
        dk = hashlib.pbkdf2_hmac(alg, plain.encode("utf-8"), salt, it, len(expected))
        return _hmac.compare_digest(dk, expected)
    except Exception:
        return False


# ── passphrase 生成 ─────────────────────────────────────
def generate_passphrase() -> str:
    """
    格式 A:  <word>-<word>-<word>-<NN>   e.g.  sunset-dragon-forge-42
    三词独立采样（允许罕见重复），数字 10-99。
    """
    w = [secrets.choice(WORDS) for _ in range(3)]
    n = secrets.randbelow(90) + 10  # 10..99
    return "{}-{}-{}-{:02d}".format(w[0], w[1], w[2], n)


# ── policy 帮助 ──────────────────────────────────────────
def make_password_policy(password_hash: str) -> dict:
    return {
        "visibility": "password",
        "password_set_at": _now_iso(),
        "password_hash": password_hash,
    }


def make_public_policy() -> dict:
    return {"visibility": "public"}


def is_password_protected(entry: dict) -> bool:
    pol = (entry or {}).get("policy") or {}
    return pol.get("visibility") == "password" and bool(pol.get("password_hash"))


# ── cookie 名（每 doc 一个，路径隔离）────────────────────
def cookie_name(user: str, slug: str) -> str:
    return "omeshare_{}_{}".format(_slug_safe(user), _slug_safe(slug))


def _slug_safe(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── SQLite store ─────────────────────────────────────────
_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    sid         TEXT PRIMARY KEY,
    user        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    ip          TEXT,
    ua          TEXT,
    revoked     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_doc ON sessions(user, slug);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS failed_attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    ip          TEXT,
    ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fa_doc_ts ON failed_attempts(user, slug, ts);
CREATE INDEX IF NOT EXISTS idx_fa_ip_ts ON failed_attempts(user, slug, ip, ts);

CREATE TABLE IF NOT EXISTS audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    user        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    event       TEXT NOT NULL,
    sid         TEXT,
    ip          TEXT,
    ua          TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_doc_ts ON audit(user, slug, ts);
"""


class AuthStore:
    """所有 SQL 走 self._lock。简单够用，单租户量级不会拥塞。"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(_DDL)
            c.commit()

    def _conn(self):
        # check_same_thread=False 配合外层 self._lock 保证线程安全
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    # ── sessions ──
    def create_session(self, user: str, slug: str, ip: str, ua: str,
                       ttl_seconds: int) -> Tuple[str, str]:
        sid = secrets.token_urlsafe(32)
        now = _now_iso()
        exp = _iso_after_seconds(ttl_seconds)
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO sessions(sid,user,slug,created_at,last_seen,expires_at,ip,ua,revoked)"
                " VALUES(?,?,?,?,?,?,?,?,0)",
                (sid, user, slug, now, now, exp, ip, ua),
            )
            c.commit()
        return sid, exp

    def get_session(self, sid: str) -> Optional[sqlite3.Row]:
        if not sid:
            return None
        with self._lock, self._conn() as c:
            row = c.execute("SELECT * FROM sessions WHERE sid=?", (sid,)).fetchone()
            return row

    def touch_session(self, sid: str, new_expires_at: str):
        with self._lock, self._conn() as c:
            c.execute(
                "UPDATE sessions SET last_seen=?, expires_at=? WHERE sid=? AND revoked=0",
                (_now_iso(), new_expires_at, sid),
            )
            c.commit()

    def list_sessions(self, user: str, slug: str) -> List[dict]:
        now = _now_iso()
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT sid, created_at, last_seen, expires_at, ip, ua FROM sessions"
                " WHERE user=? AND slug=? AND revoked=0 AND expires_at>?"
                " ORDER BY last_seen DESC",
                (user, slug, now),
            ).fetchall()
        return [dict(r) for r in rows]

    def revoke_session(self, sid: str):
        with self._lock, self._conn() as c:
            c.execute("UPDATE sessions SET revoked=1 WHERE sid=?", (sid,))
            c.commit()

    def revoke_all_sessions(self, user: str, slug: str) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute(
                "UPDATE sessions SET revoked=1 WHERE user=? AND slug=? AND revoked=0",
                (user, slug),
            )
            c.commit()
            return cur.rowcount

    def purge_expired(self, keep_days: int = 30):
        """过期 + 30 天前旧记录清理（audit 保留更长）"""
        cutoff = _iso_before_seconds(keep_days * 86400)
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM sessions WHERE expires_at<?", (_now_iso(),))
            c.execute("DELETE FROM failed_attempts WHERE ts<?", (cutoff,))
            c.commit()

    # ── failed_attempts + 速率限制 ──
    def record_fail(self, user: str, slug: str, ip: str):
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO failed_attempts(user,slug,ip,ts) VALUES(?,?,?,?)",
                (user, slug, ip, _now_iso()),
            )
            c.commit()

    def _count_fails(self, user: str, slug: str, ip: Optional[str], since: str) -> int:
        with self._lock, self._conn() as c:
            if ip:
                row = c.execute(
                    "SELECT COUNT(*) AS n FROM failed_attempts"
                    " WHERE user=? AND slug=? AND ip=? AND ts>=?",
                    (user, slug, ip, since),
                ).fetchone()
            else:
                row = c.execute(
                    "SELECT COUNT(*) AS n FROM failed_attempts"
                    " WHERE user=? AND slug=? AND ts>=?",
                    (user, slug, since),
                ).fetchone()
            return int(row["n"])

    def check_rate_limit(self, user: str, slug: str, ip: str) -> Optional[str]:
        """
        返回 None 通行；返回 str 为锁定原因（给前端展示）。
        三层：IP×doc 5/10min；doc 50/1h；doc 500/日。
        """
        now = time.time()
        n_ip = self._count_fails(user, slug, ip, _iso_before_seconds(600))
        if n_ip >= 5:
            return "ip_locked"
        n_doc_hour = self._count_fails(user, slug, None, _iso_before_seconds(3600))
        if n_doc_hour >= 50:
            return "doc_cooldown"
        n_doc_day = self._count_fails(user, slug, None, _iso_before_seconds(86400))
        if n_doc_day >= 500:
            return "doc_locked"
        return None

    def rate_limit_snapshot(self, user: str, slug: str, ip: str) -> dict:
        """给设置页抽屉展示当前各计数器。"""
        return {
            "ip_10min": self._count_fails(user, slug, ip, _iso_before_seconds(600)),
            "doc_1hour": self._count_fails(user, slug, None, _iso_before_seconds(3600)),
            "doc_1day": self._count_fails(user, slug, None, _iso_before_seconds(86400)),
        }

    # ── audit ──
    def log(self, user: str, slug: str, event: str,
            sid: Optional[str] = None, ip: Optional[str] = None, ua: Optional[str] = None):
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO audit(ts,user,slug,event,sid,ip,ua) VALUES(?,?,?,?,?,?,?)",
                (_now_iso(), user, slug, event, sid, ip, ua),
            )
            c.commit()

    def tail_audit(self, user: str, slug: str, limit: int = 20) -> List[dict]:
        limit = max(1, min(int(limit), 200))
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT ts,event,sid,ip,ua FROM audit"
                " WHERE user=? AND slug=? ORDER BY id DESC LIMIT ?",
                (user, slug, limit),
            ).fetchall()
        return [dict(r) for r in rows]


def _iso_after_seconds(sec: int) -> str:
    t = datetime.now(timezone.utc).timestamp() + sec
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_before_seconds(sec: int) -> str:
    t = datetime.now(timezone.utc).timestamp() - sec
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
