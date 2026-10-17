#!/usr/bin/env bash
## Initialize git submodules on session start.
## `claude --worktree` creates the worktree but does NOT populate submodules, so
## a session started there sees empty submodule directories. Cheap no-op for
## repos without submodules or already-initialized ones.
##
## Never blocks session start. On failure it says so on stdout, which SessionStart
## surfaces as context — an agent working against empty submodules and not knowing
## is exactly the silent-wrong-state failure this is meant to prevent.

set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-$PWD}" 2>/dev/null || exit 0

[ -f .gitmodules ] || exit 0

## `git submodule status` prefixes uninitialized entries with '-'.
git submodule status 2>/dev/null | grep -q '^-' || exit 0

if out="$(git submodule update --init --recursive 2>&1)"; then
  exit 0
fi

echo "WARNING: submodule init failed in this worktree — these directories are EMPTY:"
git submodule status 2>/dev/null | awk '/^-/{print "  " $2}'
echo "Do not assume their contents exist. Cause:"
echo "$out" | tail -3 | sed 's/^/  /'
exit 0
