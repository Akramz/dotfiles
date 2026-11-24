#!/usr/bin/env bash
# Lint, then install a copy of the repo into a throwaway $HOME and check its links with doctor.
set -euo pipefail
cd "$(dirname "$0")"

echo "== shellcheck"
git ls-files -z | xargs -0 grep -lE '^#!/(usr/bin/env |bin/)(ba)?sh' | xargs shellcheck -S warning

echo "== ruff"
{ git ls-files '*.py'; git ls-files -z | xargs -0 grep -lE '^#!/usr/bin/env python'; } | sort -u \
  | xargs uvx ruff check --isolated -q --select E9,F

echo "== json"
git ls-files '*.json' ':!vscode/' | while read -r f; do jq empty "$f" 2>/dev/null || { echo "bad JSON: $f"; exit 1; }; done

echo "== sandbox install"
sandbox="$(mktemp -d)"
trap 'rm -rf "$sandbox"' EXIT
git ls-files -co --exclude-standard -z | rsync -a --from0 --files-from=- . "$sandbox/repo"
mkdir -p "$sandbox/repo/.git/info"
export HOME="$sandbox/home" DOTFILES_SANDBOX=1
run() {
  local log="$sandbox/$1.log"; shift
  "$sandbox/repo/install.sh" "$@" >"$log" 2>&1 || { cat "$log"; exit 1; }
}
run first link --with-work
run second link
grep -q '^0 change(s), 0 failure(s)' "$sandbox/second.log" || { echo "second run was not a no-op:"; cat "$sandbox/second.log"; exit 1; }
run doctor doctor
echo "verify: ok ($(grep -c '·' "$sandbox/doctor.log") checks clear)"
