#!/bin/sh
## Mirror every project's auto-memory folder (~/.claude/projects/<key>/memory)
## into the private memories clone at dotfiles/claude-memory/projects/<key>/memory,
## so the repo's history covers all projects, not just the ones that set
## autoMemoryDirectory. -R keeps --delete inside each memory folder, so other
## machines' <key> folders in the same repo are never touched.

repo="$(dirname "$(readlink -f "$0")")/../../claude-memory"
[ -d "$repo/.git" ] || exit 0
cd "$HOME/.claude/projects" || exit 0
find . -mindepth 2 -maxdepth 2 -type d -name memory ! -empty \
  -exec sh -c 'rsync -aR --delete "$@" "$0"' "$repo/projects/" {} + >/dev/null 2>&1
exit 0
