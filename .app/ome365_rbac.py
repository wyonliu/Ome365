"""
ome365.rbac · v1.1.2 P1 #7 · role-based access control
[decision: 2026-05-09-v1-1-2-final-batch]

3 roles: owner / contributor / viewer
Config: vault/.ome365/roles.yml (gitignored optional)

  default_role: contributor
  members:
    alice:  owner
    bob:    contributor
    carol:  viewer

Permissions matrix:
  owner       — read · write · delete · admin (config / roles)
  contributor — read · write
  viewer      — read

Used by ome365_decisions / ome365_eval HTTP routes for can_X checks.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

try:
    import yaml
except ImportError:
    yaml = None


Role = Literal["owner", "contributor", "viewer"]
Action = Literal["read", "write", "delete", "admin"]

PERMISSIONS: dict[Role, set[Action]] = {
    "owner":       {"read", "write", "delete", "admin"},
    "contributor": {"read", "write"},
    "viewer":      {"read"},
}


def _vault_root(vault: Optional[Path] = None) -> Path:
    if vault:
        return Path(vault).resolve()
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


def load_roles(vault: Optional[Path] = None) -> dict:
    """Load roles config · {default_role, members: {<actor>: <role>}}.
    Defaults to {"default_role": "contributor", "members": {}} if missing."""
    v = _vault_root(vault)
    cfg_fp = v / ".ome365" / "roles.yml"
    if not cfg_fp.exists():
        return {"default_role": "contributor", "members": {}}
    if yaml:
        try:
            data = yaml.safe_load(cfg_fp.read_text("utf-8")) or {}
            if not isinstance(data, dict):
                return {"default_role": "contributor", "members": {}}
            data.setdefault("default_role", "contributor")
            data.setdefault("members", {})
            return data
        except yaml.YAMLError:
            return {"default_role": "contributor", "members": {}}
    # Fallback: simple line parser (no PyYAML)
    out: dict = {"default_role": "contributor", "members": {}}
    in_members = False
    for line in cfg_fp.read_text("utf-8").splitlines():
        s = line.strip()
        if s.startswith("default_role:"):
            out["default_role"] = s.split(":", 1)[1].strip().strip("'\"")
        elif s == "members:":
            in_members = True
        elif in_members and ":" in s:
            k, v_ = s.split(":", 1)
            out["members"][k.strip()] = v_.strip().strip("'\"")
    return out


def role_of(actor: str, vault: Optional[Path] = None) -> Role:
    """Returns role for actor · falls back to default_role."""
    cfg = load_roles(vault)
    members = cfg.get("members") or {}
    role = members.get(actor) or cfg.get("default_role", "contributor")
    if role not in PERMISSIONS:
        role = "contributor"
    return role  # type: ignore[return-value]


def can(actor: str, action: Action, vault: Optional[Path] = None) -> bool:
    """True if actor has permission for action."""
    return action in PERMISSIONS[role_of(actor, vault)]


def require(actor: str, action: Action, vault: Optional[Path] = None) -> None:
    """Raise PermissionError if actor lacks permission."""
    if not can(actor, action, vault):
        raise PermissionError(
            f"actor '{actor}' (role={role_of(actor, vault)}) cannot {action}"
        )


def cli_main(argv: list[str]) -> int:
    """`./ome365 rbac who <actor> | list | check <actor> <action>` · ops debug."""
    import json
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "usage:\n"
            "  ome365 rbac who <actor>                # actor's role + permissions\n"
            "  ome365 rbac list                       # all configured members\n"
            "  ome365 rbac check <actor> <action>     # exit 0 if allowed, 1 if denied\n"
            "                                         # action: read|write|delete|admin\n",
            flush=True,
        )
        return 0

    cmd = argv[0]

    if cmd == "who":
        if len(argv) < 2:
            print("ERROR: ome365 rbac who <actor>", flush=True)
            return 2
        actor = argv[1]
        role = role_of(actor)
        perms = sorted(PERMISSIONS[role])
        print(json.dumps({
            "actor": actor,
            "role": role,
            "permissions": perms,
        }, indent=2))
        return 0

    if cmd == "list":
        cfg = load_roles()
        print(json.dumps({
            "default_role": cfg.get("default_role", "contributor"),
            "members": cfg.get("members", {}),
        }, indent=2, ensure_ascii=False))
        return 0

    if cmd == "check":
        if len(argv) < 3:
            print("ERROR: ome365 rbac check <actor> <action>", flush=True)
            return 2
        actor, action = argv[1], argv[2]
        if action not in ("read", "write", "delete", "admin"):
            print(f"ERROR: action must be read|write|delete|admin, got {action!r}", flush=True)
            return 2
        if can(actor, action):  # type: ignore[arg-type]
            print(f"allow  · {actor} ({role_of(actor)}) can {action}")
            return 0
        print(f"deny   · {actor} ({role_of(actor)}) cannot {action}")
        return 1

    print(f"ERROR: unknown subcommand '{cmd}' (try who | list | check)", flush=True)
    return 2


__all__ = ["Role", "Action", "PERMISSIONS", "load_roles", "role_of", "can", "require", "cli_main"]
