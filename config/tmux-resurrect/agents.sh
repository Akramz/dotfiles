#!/usr/bin/env bash
# tmux-resurrect save strategy (linked into its save_command_strategies/).
# Like the default ps strategy, except tp starts agents as the pane's own
# process rather than under a shell, so a non-shell pane saves itself.
# claude and copilot panes save a command that reopens their own chat by ID,
# or a fresh start when none is found; --continue would reopen whichever chat
# is newest in the directory.

pid="$1"
case "$(ps -o comm= -p "$pid")" in
  *sh) pid="$(pgrep -P "$pid" | head -1)" ;;
esac
[ -z "$pid" ] && exit 0

args="$(ps -ww -o args= -p "$pid")"
# A cld/pc/oa NAME host:dir pane: rerun its ssh, which reattaches to the agent on the host.
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
  claude|copilot) shift ;;
  *) printf '%s\n' "$args"; exit 0 ;;
esac

# Drop old resume flags so they don't pile up across restarts.
out="$agent"
while [ $# -gt 0 ]; do
  case "$1" in
    -c|--continue|--fork-session|--resume=*|--session-id=*) ;;
    -r|--resume|--session-id) case "${2:-}" in ""|-*) ;; *) shift ;; esac ;;
    *) out="$out $1" ;;
  esac
  shift
done

if [ "$agent" = claude ]; then
  id="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["sessionId"])' \
    "$HOME/.claude/sessions/$pid.json" 2>/dev/null)"
  [ -n "$id" ] && ls "$HOME"/.claude/projects/*/"$id".jsonl >/dev/null 2>&1 &&
    out="$out --resume $id"
else
  # Newer copilot holds its session's inuse.<pid>.hold open.
  id="$(lsof -n -P -w -a -p "$pid" -Fn 2>/dev/null |
    sed -n 's|^n.*/session-state/\([^/]*\)/inuse\..*|\1|p' | head -1)"
  if [ -n "$id" ]; then
    [ -s "$HOME/.copilot/session-state/$id/events.jsonl" ] && out="$out --resume=$id"
  # Older copilot: the newest locked session with a chat named in this pid's logs.
  elif cd "$HOME/.copilot" 2>/dev/null; then
    chats="$(cat logs/process-*-"$pid".log logs/process-*-"$pid".*.log 2>/dev/null |
      grep -oE '[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}' | sort -u |
      while read -r i; do
        if [ -e "session-state/$i/inuse.$pid.lock" ] && [ -s "session-state/$i/events.jsonl" ]; then
          echo "session-state/$i/events.jsonl"
        fi
      done)"
    [ -n "$chats" ] && out="$out --resume=$(ls -t $chats | head -1 | cut -d/ -f2)"
  fi
fi
printf '%s\n' "$out"
