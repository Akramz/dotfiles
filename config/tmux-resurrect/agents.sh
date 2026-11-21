#!/usr/bin/env bash
# tmux-resurrect save strategy (linked into its save_command_strategies/).
# Like the default ps strategy, except tp starts agents as the pane's own
# process rather than under a shell, so a non-shell pane saves itself.
# claude and pi panes save a command that reopens their own chat by ID,
# or a fresh start when none is found; --continue would reopen whichever chat
# is newest in the directory.

pid="$1"
case "$(ps -o comm= -p "$pid")" in
  *sh) pid="$(pgrep -P "$pid" | head -1)" ;;
esac
[ -z "$pid" ] && exit 0

args="$(ps -ww -o args= -p "$pid")"
# A cld/pie NAME host:dir pane: rerun its ssh, which reattaches to the agent on the host.
# ssh joins its command words with spaces, so these flattened args lose nothing.
case "$args" in
  "ssh -t "*new-session*)
    rest="${args#ssh -t }"
    printf 'ssh -t %s %q\n' "${rest%% *}" "${rest#* }"; exit 0 ;;
esac
set -f; set -- $args; set +f
case "${1##*/}" in node*|python*|Python|bun|deno) shift ;; esac
agent="${1##*/}"
case "$agent" in
  claude|pi) shift ;;
  *) printf '%s\n' "$args"; exit 0 ;;
esac

# Drop old resume flags so they don't pile up across restarts.
out="$agent"
while [ $# -gt 0 ]; do
  case "$1" in
    -c|--continue|--fork-session) ;;
    -r|--resume|--session-id|--session) case "${2:-}" in ""|-*) ;; *) shift ;; esac ;;
    *) out="$out $1" ;;
  esac
  shift
done

if [ "$agent" = pi ]; then
  # pi/extensions/claude-hooks.ts writes the session file of each pi process here.
  f="$(cat "$HOME/.pi/agent/pids/$pid" 2>/dev/null)"
  [ -s "$f" ] && out="$out --session $f"
else
  id="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["sessionId"])' \
    "$HOME/.claude/sessions/$pid.json" 2>/dev/null)"
  [ -n "$id" ] && ls "$HOME"/.claude/projects/*/"$id".jsonl >/dev/null 2>&1 &&
    out="$out --resume $id"
fi
printf '%s\n' "$out"
