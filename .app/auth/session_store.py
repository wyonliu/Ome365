"""
Ome365 · Session Store · SQLite-backed

为什么选 SQLite 而不是 JWT：
- JWT 不能撤销（logout 只能删 cookie，服务端无法吊销），对 PKM 场景风险太大
- JWT payload 里放 email/role 会泄露给 client，哪怕签名了
- SQLite 单文件、无需额外进程、zero-config，跟当前「文件系统即数据库」一致

为什么不用 Redis：
- 多一个运维组件，家庭/单人部署不划算
- 企业部署需要 Redis 时可以换 store 实现（Protocol 兼容）

表 schema: sessions(sid TEXT PK, user_json TEXT, tenant_id TEXT, expires_at REAL, created_at REAL)
"""
from __future__ import annotations

import json
import sqlite3
import secrets
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .base import Session, User


class SessionStore:
    """SQLite 实现的 session 存储。线程安全。"""

    def __init__(self, db_path: Path, default_ttl_hours: int = 720):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_ttl = timedelta(hours=default_ttl_hours)
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self):
        return sqlite3.connect(str(self.db_path), isolation_level=None)

    def _init_db(self):
        with self._lock, self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS sessions ("
                "  sid TEXT PRIMARY KEY,"
                "  user_json TEXT NOT NULL,"
                "  tenant_id TEXT NOT NULL,"
                "  expires_at REAL NOT NULL,"
                "  created_at REAL NOT NULL"
                ")"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)"
            )

    def create(self, user: User, ttl: Optional[timedelta] = None) -> Session:
        sid = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        ttl = ttl or self.default_ttl
        sess = Session(
            sid=sid,
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            expires_at=now + ttl,
            created_at=now,
            data={"user": user.to_dict()},
        )
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO sessions(sid, user_json, tenant_id, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (sid, json.dumps(sess.data, ensure_ascii=False), user.tenant_id,
                 sess.expires_at.timestamp(), now.timestamp()),
            )
        return sess

    def get(self, sid: str) -> Optional[Session]:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT sid, user_json, tenant_id, expires_at, created_at FROM sessions WHERE sid = ?",
                (sid,),
            ).fetchone()
        if not row:
            return None
        sid_, user_json, tenant_id, expires_at, created_at = row
        sess = Session(
            sid=sid_,
            user_id=json.loads(user_json)["user"]["user_id"],
            tenant_id=tenant_id,
            expires_at=datetime.utcfromtimestamp(expires_at),
            created_at=datetime.utcfromtimestamp(created_at),
            data=json.loads(user_json),
        )
        if sess.is_expired():
            self.delete(sid)
            return None
        return sess

    def get_user(self, sid: str) -> Optional[User]:
        sess = self.get(sid)
        if not sess:
            return None
        return User.from_dict(sess.data["user"])

    def delete(self, sid: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM sessions WHERE sid = ?", (sid,))

    def delete_for_user(self, tenant_id: str, user_id: str) -> int:
        """用于 user 改密 / 踢所有设备。返回删除的行数。"""
        with self._lock, self._conn() as c:
            cur = c.execute(
                "DELETE FROM sessions WHERE tenant_id = ? AND json_extract(user_json, '$.user.user_id') = ?",
                (tenant_id, user_id),
            )
            return cur.rowcount

    def gc(self) -> int:
        """清理过期 session。建议定时调用或启动时调一次。"""
        with self._lock, self._conn() as c:
            cur = c.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.utcnow().timestamp(),))
            return cur.rowcount

    def count(self) -> int:
        with self._lock, self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
