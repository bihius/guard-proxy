#!/usr/bin/env bash
# Links shared dev assets from the main repo into a git worktree.
# Run automatically via Claude Code PostToolUse hook, or manually:
#
#   bash scripts/setup-worktree.sh [worktree-path]
#
# If worktree-path is omitted, uses the repo root of the current directory.

set -euo pipefail

WORKTREE_ROOT="${1:-$(git rev-parse --show-toplevel)}"
WORKTREE_ROOT="$(cd "$WORKTREE_ROOT" && pwd)"

# --git-common-dir points to the main repo's .git regardless of which worktree we're in
GIT_COMMON="$(git -C "$WORKTREE_ROOT" rev-parse --git-common-dir)"
[[ "$GIT_COMMON" == /* ]] || GIT_COMMON="$WORKTREE_ROOT/$GIT_COMMON"
MAIN_ROOT="$(cd "$GIT_COMMON/.." && pwd)"

if [[ "$WORKTREE_ROOT" == "$MAIN_ROOT" ]]; then
  echo "setup-worktree: already in main repo — nothing to link."
  exit 0
fi

echo "setup-worktree: worktree → $WORKTREE_ROOT"
echo "setup-worktree: main repo → $MAIN_ROOT"

link_or_skip() {
  local target="$1" link="$2" label="$3"
  if [[ -L "$link" ]]; then
    echo "  $label: already linked (skipping)"
  elif [[ -e "$link" ]]; then
    echo "  $label: real path exists — skipping (remove manually if you want a symlink)"
  elif [[ -e "$target" ]]; then
    ln -s "$target" "$link"
    echo "  $label: linked ✓"
  else
    echo "  $label: source not found at $target — skipping"
  fi
}

link_or_skip \
  "$MAIN_ROOT/src/frontend/node_modules" \
  "$WORKTREE_ROOT/src/frontend/node_modules" \
  "frontend/node_modules"

link_or_skip \
  "$MAIN_ROOT/src/backend/.env" \
  "$WORKTREE_ROOT/src/backend/.env" \
  "backend/.env"

echo "setup-worktree: done."
