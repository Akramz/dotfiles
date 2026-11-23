# Homebrew: /opt/homebrew on the Mac, /home/linuxbrew/.linuxbrew on Linux.
for _brew in /opt/homebrew/bin/brew /home/linuxbrew/.linuxbrew/bin/brew; do
  [[ -x $_brew ]] && { eval "$($_brew shellenv)"; break; }
done; unset _brew
# brew shellenv exports FPATH, so every nested shell (tmux, agents) inherits and grows it;
# oh-my-zsh then sees a new fpath and rebuilds its completion cache (0.5 s) on each start.
typeset +x FPATH; typeset -U path fpath
# ~/bin first: ~/bin/gh wraps brew's gh to pick the GitHub account per repo.
path=("$HOME/bin" $path)

# oh-my-zsh, no theme: PROMPT below is the whole prompt.
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME=""
plugins=(git zsh-autosuggestions autojump tmux)

source $ZSH/oh-my-zsh.sh

PROMPT='%~ %# '
# Over ssh, show the host so a remote shell is never mistaken for the local one.
[[ -n $SSH_CONNECTION ]] && PROMPT='%m:%~ %# '

command -v rbenv >/dev/null && eval "$(rbenv init -)"
alias tnew='tmux new-session -s'
alias tls='tmux list-sessions'
alias tattach='tmux attach-session -t'
alias tkill='tmux kill-session -t'
# _tp_new NAME DIR CMD — create a tmux session running CMD in DIR (nesting-aware) and enter it.
# Sessions run in the checkout as it stands; nothing here creates a worktree or a branch.
# DIR as host:dir (not a local folder) runs it on that ssh host instead.
_tp_new() {
  if [[ ! -d $2 ]]; then
    [[ $2 == *:* ]] && { _tp_new_remote "$@"; return }
    print -u2 "no such folder: $2"; return 1
  fi
  if [[ -n $TMUX ]]; then
    command tmux new-session -d -s "$1" -c "$2" "$3" \
      && command tmux switch-client -t "$1"
  else
    command tmux new-session -s "$1" -c "$2" "$3"
  fi
}
# _tp_new_remote NAME HOST:DIR CMD — run CMD in tmux session NAME on HOST, inside a local
# session NAME@HOST so tp lists it. The remote session outlives ssh; rerunning reattaches.
# A relative DIR is under the remote ~. Runs in zsh if the host has it, else the login shell;
# -i because on Linux brew (and its tmux) is only on PATH in interactive shells.
# A failed launch stays on screen for 5s.
_tp_new_remote() {
  local host=${2%%:*} dir=${2#*:}
  [[ $dir == /* ]] && dir=${(q)dir} || dir="~/${(q)${dir#\~/}}"
  local inner="{ tmux ls || { pkill -USR1 -u \$(id -u) -x 'tmux: server' && sleep 0.2; }; } >/dev/null 2>&1; cd $dir && exec tmux new-session -A -s ${(q)1} ${(q)3}"
  local rcmd="exec \"\$(command -v zsh || echo \"\$SHELL\")\" -ilc ${(q)inner}"
  _tp_new "$1@$host" "$PWD" "ssh -t ${(q)host} ${(q)rcmd} || sleep 5"
}
# tp [name] — project-grouped tmux session picker (TUI: ~/.config/tp/tp_tui.py)
# with a name: attach if that session exists, else open the picker filtered by it
tp() {
  local tmpf action
  if [[ -n $* ]] && command tmux has-session -t "=$*" 2>/dev/null; then
    action="attach"$'\t'"$*"
  else
    tmpf=$(command mktemp -t tp.XXXXXX) || return
    TP_RESULT_FILE="$tmpf" command python3 "$HOME/.config/tp/tp_tui.py" "$@"
    action="$(<"$tmpf")"
    command rm -f "$tmpf"
  fi
  [[ -z $action ]] && return 0
  local -a parts
  parts=("${(@ps:\t:)action}")
  case "$parts[1]" in
    attach)
      # Several picks: the rest go to the next Ghostty splits first.
      if (( $#parts > 2 )) && [[ -x $HOME/bin/ghostty_panes.py ]]; then
        "$HOME/bin/ghostty_panes.py" open "${(@)parts[3,-1]}"
      fi
      if [[ -n $TMUX ]]; then
        command tmux switch-client -t "$parts[2]"
      else
        command tmux attach-session -t "$parts[2]"
      fi
      ;;
    create)
      pie "$parts[3]" "$parts[2]"
      ;;
  esac
}

# _tp_launch CMD DEFAULT_NAME ARGS…
_tp_launch() {
  local cmd=$1 def=$2; shift 2
  local -a args=("${@:#-*}")
  local dir=${args[2]:-$PWD}
  [[ -d $dir ]] && dir=${dir:a}
  set -- ${(M)@:#-*}
  _tp_new "${args[1]:-$def}" "$dir" "$cmd ${(j: :)${(q)@}}"
}
# TAB on the path: local folders and ssh hosts, then folders on that host (as scp completes them)
_tp_launch_complete() {
  local -a before=(${words[2,CURRENT-1]:#-*})
  (( $#before == 1 )) || return 1
  if compset -P 1 '*:'; then _remote_files -/ -- ssh
  else _alternative 'folders:folder:_path_files -/' 'hosts:host:_ssh_hosts -S:'
  fi
}
# cld / pie <name> [dir | host:dir] [--flag…]   new Claude / pi session in dir
# (default: here), or on an ssh host (host: alone is its ~); dash args go to the CLI
cld() { _tp_launch 'claude --permission-mode auto' '' "$@" }
pie() { _tp_launch pi pi "$@" }
compdef _tp_launch_complete cld pie
# adm [name] — the pi session in ~ for mail, calendar and other admin; attaches if it exists.
# pi reads Claude's memory (pi/extensions/claude-context.ts), so admin work need not spend Claude budget.
adm() {
  local n=${1:-admin}
  if command tmux has-session -t "=$n" 2>/dev/null; then tp "$n"; else pie "$n" ~; fi
}

# vcp — copy files or folders to or from a VM. dest is always a folder; a trailing / never matters.
#   pull: dest defaults to here.  push: dest defaults to the same folder under ~ as here.
# `function` form: the noglob alias below would break `vcp()` when .zshrc is re-sourced.
function vcp {
  if [[ ! -e $1 && $1 == *:* ]]; then
    local dest=${2:-.}
    mkdir -p "$dest" && rsync -aP "${1%/}" "$dest/"
    return
  fi
  (( $# >= 2 )) || { echo "usage: vcp host:path [dest] | vcp path… host[:dest]" >&2; return 2; }
  local -a src=(${~@[1,-2]})
  local t=${@[-1]}; local host=${t%%:*}; local dest=${${t#$host}#:}
  dest=${${dest#\~/}%/}
  if [[ -z $dest ]]; then
    [[ $PWD == $HOME/* ]] && dest=${PWD#$HOME/} || dest=.
  fi
  echo "→ $host:$dest/"
  rsync -aP --rsync-path="mkdir -p '$dest' && rsync" "${src[@]%/}" "$host:$dest/"
}
# Remote globs (vcp vm:runs/*.tif) reach the VM as typed; local ones expand in vcp.
alias vcp='noglob vcp'
compdef vcp=scp

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
alias z=j
unsetopt AUTO_CD

# cd or z lists the new folder; only at a terminal, so agents' shells stay quiet.
_ls_after_cd() { [[ -t 1 ]] && ls }
autoload -Uz add-zsh-hook
add-zsh-hook chpwd _ls_after_cd

# up — update brew and the agent CLIs in one go; stops at the first failure.
up() { brew update && brew upgrade && brew autoremove && command claude update }

# Claude Code: use the system rg instead of its bundled one
export USE_BUILTIN_RIPGREP=0
export PATH="$PATH:$HOME/go/bin"

# For Claude
export CLAUDE_CODE_NO_FLICKER=1
# Claude Code + pi usage figure: agent-usage [SINCE UNTIL] (default last Mon–Sat)
alias agent-usage='"$HOME/bin/agent_usage.py"'

# macOS-only bits.
if [[ $OSTYPE == darwin* ]]; then
  export PATH="$PATH:/Applications/Visual Studio Code.app/Contents/Resources/app/bin"
  # Revive Ghostty's global ctrl+space hotkey after macOS kills its event tap
  alias poke-ghostty='bash "$HOME/bin/poke_ghostty.sh"'
  # Opt+Shift+<n> in a split with no tmux: Ghostty sends ESC[901<n>~. Detached
  # and nohup'd, since resizing may close this very split.
  _ghostty_panes() { nohup "$HOME/bin/ghostty_panes.py" "${KEYS[6]}" >/dev/null 2>&1 &! }
  zle -N _ghostty_panes
  for n in {1..9}; do bindkey "\e[901${n}~" _ghostty_panes; done
fi

# Your own aliases: personal/zshrc, linked here by install.sh.
[[ -f "$HOME/.config/zsh/local.zsh" ]] && source "$HOME/.config/zsh/local.zsh"
