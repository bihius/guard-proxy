#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# worktree-dev.sh — run Vite dev servers for every git worktree
#
# Each worktree gets its own port starting at BASE_PORT (default 3000).
# The main worktree gets 3000, the next 3001, etc.
#
# Usage:
#   ./scripts/worktree-dev.sh          # all worktrees, starting at 3000
#   ./scripts/worktree-dev.sh 4000     # all worktrees, starting at 4000
#   ./scripts/worktree-dev.sh 3000 2   # only launch for worktree at index 2
# ──────────────────────────────────────────────────────────────
set -euo pipefail

BASE_PORT="${1:-3000}"
ONLY_INDEX="${2:-}"       # optional: run only this worktree index
FRONTEND_REL="src/frontend"
PIDS=()

cleanup() {
  echo ""
  echo "Stopping all dev servers…"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

mapfile -t WORKTREES < <(git worktree list --porcelain | grep '^worktree ' | sed 's/^worktree //')

if [[ ${#WORKTREES[@]} -eq 0 ]]; then
  echo "No git worktrees found."
  exit 1
fi

echo "Found ${#WORKTREES[@]} worktree(s):"
echo ""

PORT=$BASE_PORT
INDEX=0

for wt in "${WORKTREES[@]}"; do
  FRONTEND_DIR="$wt/$FRONTEND_REL"

  if [[ -n "$ONLY_INDEX" && "$INDEX" -ne "$ONLY_INDEX" ]]; then
    PORT=$((PORT + 1))
    INDEX=$((INDEX + 1))
    continue
  fi

  if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "  [$INDEX] SKIP  $wt  (no $FRONTEND_REL)"
    PORT=$((PORT + 1))
    INDEX=$((INDEX + 1))
    continue
  fi

  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "  [$INDEX] Installing dependencies in $FRONTEND_DIR …"
    (cd "$FRONTEND_DIR" && pnpm install --frozen-lockfile 2>&1 | tail -1)
  fi

  BRANCH=$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "detached")
  echo "  [$INDEX] START  :$PORT  $BRANCH  $wt"

  (cd "$FRONTEND_DIR" && PORT=$PORT pnpm run dev -- --port "$PORT" --strictPort) &
  PIDS+=($!)

  PORT=$((PORT + 1))
  INDEX=$((INDEX + 1))
done

echo ""
echo "All servers launched. Press Ctrl+C to stop."
echo ""

wait
