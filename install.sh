#!/usr/bin/env bash
# Ome365 · One-line remote installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh
#
# Env vars (all optional):
#   OME365_DIR       Install directory (default ~/Ome365)
#   OME365_REPO      Git repo (default https://github.com/wyonliu/Ome365.git)
#   OME365_BRANCH    Branch (default main)
#   OME365_NO_START  Set to 1: clone only, don't start (CI / install-only)
#   OME365_DRY_RUN   Set to 1: print plan, don't execute (safe preview)
#
# What it does:
#   1. Detect platform (macOS / Linux / WSL) + check git / python3 ≥ 3.9
#   2. Clone (or pull-update) repo to $OME365_DIR
#   3. Execute ./ome365 (first-run installs deps, starts service, opens browser)
#
# Tested on: macOS 13+ · Ubuntu 22.04 · Debian 12 · WSL2 Ubuntu

set -euo pipefail

DIR="${OME365_DIR:-$HOME/Ome365}"
REPO="${OME365_REPO:-https://github.com/wyonliu/Ome365.git}"
BRANCH="${OME365_BRANCH:-main}"
NO_START="${OME365_NO_START:-0}"
DRY_RUN="${OME365_DRY_RUN:-0}"

say()  { printf "\033[36m[install]\033[0m %s\n" "$*"; }
ok()   { printf "\033[32m[ok]\033[0m %s\n" "$*"; }
warn() { printf "\033[33m[warn]\033[0m %s\n" "$*"; }
die()  { printf "\033[31m[fail]\033[0m %s\n" "$*" >&2; exit 1; }

# ── --dry-run support ─────────────────────────────────────
# If --dry-run passed as $1 (or OME365_DRY_RUN=1), print plan + exit 0
if [ "${1:-}" = "--dry-run" ] || [ "$DRY_RUN" = "1" ]; then
  say "DRY RUN · would do the following:"
  echo "  1. Detect platform + check git / python3 ≥ 3.9"
  echo "  2. Clone (or pull) ${REPO} (branch: ${BRANCH}) to ${DIR}"
  echo "  3. Run ./ome365 (first-run installs deps, starts service, opens browser)"
  echo ""
  echo "  Override with env vars:"
  echo "    OME365_DIR=$DIR"
  echo "    OME365_REPO=$REPO"
  echo "    OME365_BRANCH=$BRANCH"
  echo "    OME365_NO_START=$NO_START"
  ok "Dry run complete · no changes made"
  exit 0
fi

# ── Platform detection ────────────────────────────────────
UNAME_S="$(uname -s 2>/dev/null || echo Unknown)"
case "$UNAME_S" in
  Darwin)
    PLATFORM="macOS"
    ;;
  Linux)
    if grep -qiE '(microsoft|wsl)' /proc/version 2>/dev/null; then
      PLATFORM="WSL"
    else
      PLATFORM="Linux"
    fi
    ;;
  CYGWIN*|MINGW*|MSYS*)
    PLATFORM="Windows-Native"
    warn "Native Windows shell detected · WSL2 + Ubuntu strongly recommended"
    ;;
  *)
    PLATFORM="Unknown ($UNAME_S)"
    warn "Unknown platform · proceeding · please report at https://github.com/wyonliu/Ome365/issues"
    ;;
esac
say "Platform: $PLATFORM"

# ── Pre-flight: git ───────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
  case "$PLATFORM" in
    macOS) die "git not found. Install: 'xcode-select --install'" ;;
    Linux|WSL) die "git not found. Install: 'sudo apt install git' / 'sudo dnf install git'" ;;
    *) die "git not found. See https://git-scm.com/downloads" ;;
  esac
fi

# ── Pre-flight: python3 ≥ 3.9 ────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  case "$PLATFORM" in
    macOS) die "Python 3.9+ not found. Install: 'brew install python@3.11' or download from python.org" ;;
    Linux|WSL) die "Python 3.9+ not found. Install: 'sudo apt install python3 python3-venv python3-pip'" ;;
    *) die "Python 3.9+ not found. See https://www.python.org/downloads/" ;;
  esac
fi
PY_VER=$(python3 -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))')
case "$PY_VER" in
  3.9|3.1[0-9]) ok "Python $PY_VER" ;;
  *) warn "Python $PY_VER detected · 3.9+ recommended (you may hit subtle issues)" ;;
esac

# ── Pre-flight: pip ───────────────────────────────────────
if ! python3 -m pip --version >/dev/null 2>&1; then
  case "$PLATFORM" in
    Linux|WSL) warn "pip not found. Install: 'sudo apt install python3-pip'" ;;
    *) warn "pip not found · ./ome365 will try ensurepip" ;;
  esac
fi

# ── Pre-flight: lsof (used by ./ome365 for port detection) ─
if ! command -v lsof >/dev/null 2>&1; then
  case "$PLATFORM" in
    Linux|WSL) warn "lsof not found. Recommend: 'sudo apt install lsof'" ;;
    *) ;;
  esac
fi

# ── Pre-flight: writable dir ──────────────────────────────
parent_dir="$(dirname "$DIR")"
if [ ! -d "$parent_dir" ]; then
  mkdir -p "$parent_dir" || die "Cannot create parent directory $parent_dir"
fi
if [ ! -w "$parent_dir" ]; then
  die "Parent directory $parent_dir is not writable"
fi

# ── Clone or update ───────────────────────────────────────
if [ -d "$DIR/.git" ]; then
  say "Existing repo at $DIR · pulling updates"
  git -C "$DIR" fetch --quiet origin "$BRANCH" || warn "fetch failed · using local cache"
  if git -C "$DIR" diff --quiet && git -C "$DIR" diff --cached --quiet; then
    git -C "$DIR" checkout --quiet "$BRANCH" || true
    git -C "$DIR" merge --ff-only --quiet "origin/$BRANCH" 2>/dev/null || warn "ff-only merge skipped (local commits ahead?)"
  else
    warn "$DIR has uncommitted changes · skipping pull"
  fi
elif [ -e "$DIR" ]; then
  die "$DIR exists but is not a git repo · move it aside or set OME365_DIR"
else
  say "Cloning $REPO → $DIR (branch: $BRANCH)"
  git clone --quiet --branch "$BRANCH" --depth 1 "$REPO" "$DIR"
fi

# ── Entry point ───────────────────────────────────────────
cd "$DIR"
if [ ! -x ./ome365 ]; then
  chmod +x ./ome365 2>/dev/null || true
fi

if [ "$NO_START" = "1" ]; then
  ok "Installed to $DIR"
  say "Start: cd $DIR && ./ome365"
  say ""
  say "Optional v1.1 features (gated by env flags · install only what you need):"
  say "  · LLM-distilled wiki:  pip install anthropic && export OME365_WIKI_LLM=1"
  say "  · Semantic search:     pip install sqlite-vec sentence-transformers && export OME365_WIKI_VEC=1"
  say "  · See $DIR/requirements-optional.txt for details"
  exit 0
fi

# ── First run ─────────────────────────────────────────────
say "First run: ./ome365 (installs deps, starts service, opens browser)"
say ""
say "After server starts:"
say "  · Open http://localhost:3650/v1_1.html  (4-card team-brain cockpit)"
say "  · Run ./ome365 status    (vault overview)"
say "  · Run ./ome365 doctor    (12-check + 12 v1.1 module health)"
say ""
exec ./ome365
