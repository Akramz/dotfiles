#!/bin/zsh
# Rewrite text from stdin (or args) as a short, friendly, polite message and copy it to the clipboard.
# Backs the "Make friendly!" right-click Service.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

text="${*:-$(cat)}"
[[ -n "${text//[[:space:]]/}" ]] || exit 0

notify() { osascript -e 'on run a' -e 'display notification (item 1 of a) with title "Make friendly!"' -e end -- "$1" >/dev/null 2>&1; }

prompt="Rewrite the message below so the reader receives it well. Keep every point, request and fact; drop insults, sarcasm and blame. Make it short, simple, easy to understand, friendly and polite, in plain natural American English. Keep the original language if it is not English. Keep the same form (an email stays an email, a chat message stays a chat message). Output only the rewritten message, with no preamble, quotes or notes.

Message:
$text"

notify "Rewriting…" &
# JSON output: text mode hard-wraps long lines, which would break the pasted message.
raw="$(cd "${TMPDIR:-/tmp}" && copilot -p "$prompt" --model claude-haiku-5.5 --reasoning-effort low \
  --no-custom-instructions --disable-builtin-mcps --disable-client-telemetry --available-tools= \
  --output-format json 2>&1)"
out="$(printf '%s\n' "$raw" | jq -rRn '[inputs | fromjson? | select(.type == "assistant.message") | .data.content // empty] | last // empty')"
if [[ -z "$out" ]]; then
  notify "Failed: $(printf '%s\n' "$raw" | grep -v '^{' | head -1 | cut -c1-120)"
  exit 1
fi
printf '%s' "$out" | pbcopy
notify "Copied to clipboard"
