#!/usr/bin/env bash
#
# poke_ghostty.sh — revive Ghostty's global ctrl+space hotkey without quitting it.
#
# Symptom this fixes: ctrl+space stops summoning the quick terminal, and only
# works while Ghostty is already the focused app — which is useless, since the
# quick terminal is the only window Ghostty ever has.
#
# Why it happens: Ghostty's `global:` keybinds ride on a CGEventTap. macOS
# switches off any tap whose callback overruns its budget — the console log
# shows kCGEventTapDisabledByTimeout firing repeatedly on Macs where
# endpoint security software (security extensions, data-loss-prevention
# daemons) and Logi Options+ sit in the input path. Siri re-enables its own
# tap each time; Logi Options+ and Ghostty do not. Ghostty 1.3.1 cannot recover:
# `CGEventTapEnable` appears nowhere in the binary, and GlobalEventTap.enable()
# returns early while self.eventTap is non-nil, so it never notices the tap
# went dead. Once disabled, it stays disabled.
#
# The lever: AppDelegate.ghosttyConfigDidChange calls GlobalEventTap.disable()
# when the config contains no `global:` keybinds, and .enable() when it does.
# So reload once with the binding commented out (tears the tap down and nils
# eventTap), then reload again with it restored (builds a fresh, enabled tap).
# Ghostty reloads its config on SIGUSR2, so none of this needs window focus.
#
#     poke-ghostty            check, and fix if the tap is dead
#     poke-ghostty --status   report only, change nothing
#     poke-ghostty --force    rebuild the tap even if it looks healthy
#
# The config is restored from a backup by an EXIT trap, so an interrupted run
# still leaves your config exactly as it found it.

set -uo pipefail

APP_CONFIG="$HOME/Library/Application Support/com.mitchellh.ghostty/config"
DEBOUNCE=6        # ghosttyConfigDidChange ignores reloads <5s apart
POLL_TIMEOUT=15

log()  { printf '\033[1;34m[ghostty]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[ghostty]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[ghostty]\033[0m %s\n' "$*" >&2; }

PY=/usr/bin/python3
[[ -x $PY ]] || PY=$(command -v python3) || { err "no python3"; exit 1; }

MODE=fix
case "${1:-}" in
  --status) MODE=status ;;
  --force)  MODE=force ;;
  -h|--help) sed -n '3,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  "") ;;
  *) err "unknown argument: $1"; exit 2 ;;
esac

# --- Ghostty's keyboard event tap, via CGGetEventTapList. Prints "enabled" or
#     "disabled", or nothing when the app has no tap. (The struct's latency
#     fields are not reported: they are unstable enough to be meaningless —
#     successive reads show min > avg.)
tap_state() {
  "$PY" - "$1" <<'PY'
import ctypes, struct, sys
pid = int(sys.argv[1])
lib = ctypes.cdll.LoadLibrary(
    '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
n = 256
buf = ctypes.create_string_buffer(48 * n)
cnt = ctypes.c_uint32(0)
if lib.CGGetEventTapList(ctypes.c_uint32(n), buf, ctypes.byref(cnt)) != 0:
    sys.exit(1)
for i in range(cnt.value):
    tid, point, opts, mask, tpid, btpid, en, mn, av, mx = struct.unpack(
        '=III4xQiiB3xfff', buf.raw[i * 48:(i + 1) * 48])
    if tpid == pid and mask & (1 << 10):          # kCGEventKeyDown
        print("enabled" if en else "disabled")
        break
else:
    print("none")
PY
}

wait_for_state() {  # wait_for_state <pid> <state>
  local pid=$1 want=$2 i=0
  while (( i++ < POLL_TIMEOUT )); do
    [[ "$(tap_state "$pid")" == "$want" ]] && return 0
    sleep 1
  done
  return 1
}

GHOSTTY_PID=$(pgrep -f "Ghostty.app/Contents/MacOS/ghostty" | head -1)
[[ -n $GHOSTTY_PID ]] || { err "Ghostty is not running — just launch it"; exit 1; }

CONFIG=$(/usr/bin/readlink -f "$APP_CONFIG" 2>/dev/null || printf '%s' "$APP_CONFIG")
[[ -f $CONFIG ]] || { err "config not found: $CONFIG"; exit 1; }

STATE=$(tap_state "$GHOSTTY_PID")

case "$STATE" in
  enabled)  log "tap is alive (pid $GHOSTTY_PID)" ;;
  disabled) warn "tap is DISABLED — global hotkey is dead (pid $GHOSTTY_PID)" ;;
  none)     warn "no event tap at all (pid $GHOSTTY_PID)" ;;
esac

[[ $MODE == status ]] && exit 0
[[ $STATE == enabled && $MODE != force ]] && { log "nothing to do"; exit 0; }

grep -qE '^[[:space:]]*keybind[[:space:]]*=.*global:' "$CONFIG" || {
  err "no 'global:' keybind in $CONFIG — nothing to rebuild"; exit 1
}

BACKUP=$(mktemp -t poke_ghostty)
cp -p "$CONFIG" "$BACKUP"
# Interrupting between the two reloads would leave the config edited and the
# tap torn down, so put both back. Disarm first: bash runs this for TERM *and*
# then for EXIT, and a second pass would see a deleted backup — `cmp` against a
# missing file reports "differs", which would copy nothing over a good config.
restore() {
  trap - EXIT INT TERM
  [[ -f $BACKUP ]] || return 0
  if ! cmp -s "$BACKUP" "$CONFIG"; then
    cp -p "$BACKUP" "$CONFIG"
    kill -USR2 "$GHOSTTY_PID" 2>/dev/null
    warn "interrupted — config restored and Ghostty reloaded"
  fi
  rm -f "$BACKUP"
}
# A bare `trap restore INT TERM` would run the handler and then *resume* the
# script, which would carry on and copy from the backup restore() just deleted.
trap restore EXIT
trap 'restore; exit 130' INT
trap 'restore; exit 143' TERM

log "dropping global keybinds and reloading (forces disable)"
sed -i '' -E 's|^([[:space:]]*keybind[[:space:]]*=.*global:)|#poke-ghostty#\1|' "$CONFIG"
kill -USR2 "$GHOSTTY_PID"
wait_for_state "$GHOSTTY_PID" none || warn "tap did not go away; continuing anyway"

log "restoring config, waiting out the ${DEBOUNCE}s debounce"
cp -p "$BACKUP" "$CONFIG"
sleep "$DEBOUNCE"

log "reloading again (forces enable)"
kill -USR2 "$GHOSTTY_PID"
if wait_for_state "$GHOSTTY_PID" enabled; then
  log "tap rebuilt and enabled — try ctrl+space"
  exit 0
fi

err "tap did not come back (state: $(tap_state "$GHOSTTY_PID"))"
err "check Accessibility for Ghostty in System Settings > Privacy & Security"
exit 1
