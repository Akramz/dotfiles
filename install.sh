#!/usr/bin/env bash
#
# install.sh — set up, or re-sync, this machine (a Mac, or a Linux box) from
# the dotfiles repo.
#
#   ./install.sh                     every stage, in order
#   ./install.sh link macos          just those stages
#   ./install.sh doctor              verify only, changes nothing
#   ./install.sh pull                copy drifted files back into the repo
#
# Stages: brew shell link macos agents vscode python secrets rust
#         (Linux: brew shell link agents python rust)
#
# Two layers sit on top of the repo: personal/ (yours, gitignored; the first
# run copies personal.example/ there) and work/ (after one `--with-work` run,
# for good). See README, "Full install".
#
# On Linux, `brew` installs Brewfile.linux. Run `linux/setup.sh` first: it does
# the root-level prerequisites (apt packages, zsh, a user-owned Homebrew prefix)
# and then calls this script. Anything specific to one machine stays out of the
# repo — see README, "Linux".
#
# Every stage is idempotent — re-running when nothing changed prints nothing
# but "no changes". Safe to run monthly. Nothing is ever overwritten without
# a backup landing in ~/.dotfiles-backup/<timestamp>/.
#
# Deliberately not `set -e`: a failing stage should report and let the rest
# run, then exit non-zero at the end. A half-finished machine that tells you
# what broke beats one that silently stopped at step 3.

set -uo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$HOME/.dotfiles-backup/$STAMP"
WITH_WORK=0

# ── OS ──────────────────────────────────────────────────────────
# One repo, two machines. Everything OS-specific keys off these flags.
# `uname` is a function call, so the Mac branch can be dry-run from Linux:
#   bash -c 'uname(){ echo Darwin; }; export -f uname; ./install.sh doctor'
case "$(uname -s)" in
  Darwin) IS_MAC=1; OS=darwin; BREW_PREFIX=/opt/homebrew; BREWFILE=Brewfile.general; MINIFORGE_OS=MacOSX
          ALL_STAGES=(brew shell link macos agents vscode python secrets rust) ;;
  Linux)  IS_MAC=0; OS=linux;  BREW_PREFIX=/home/linuxbrew/.linuxbrew; BREWFILE=Brewfile.linux; MINIFORGE_OS=Linux
          ALL_STAGES=(brew shell link agents python rust)
          # Same as home/.zshenv: npm globals under $HOME, so npm_global works from bash too.
          export NPM_CONFIG_PREFIX="$HOME/.npm-global" PATH="$HOME/.npm-global/bin:$PATH" ;;
  *) printf 'unsupported OS: %s\n' "$(uname -s)"; exit 1 ;;
esac

# So `have brew` is true even when run from bash (linux/setup.sh, a fresh SSH).
[[ -x "$BREW_PREFIX/bin/brew" ]] && eval "$("$BREW_PREFIX/bin/brew" shellenv)"
# The installers' own bin dirs, as home/.zshenv and .zshrc add them, so a re-run
# sees what an earlier stage installed even from a shell that never read them.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.bun/bin:$PATH"

CHANGES=0
FAILURES=0

# ── output ──────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  B=$'\033[1m'; DIM=$'\033[2m'; GRN=$'\033[32m'; YLW=$'\033[33m'; RED=$'\033[31m'; RST=$'\033[0m'
else
  B=; DIM=; GRN=; YLW=; RED=; RST=
fi
stage()   { printf '\n%s══ %s %s\n' "$B" "$1" "$RST"; }
changed() { printf '  %s+%s %s\n' "$GRN" "$RST" "$1"; CHANGES=$((CHANGES + 1)); }
same()    { printf '  %s·%s %s\n' "$DIM" "$RST" "$1"; }
skip()    { printf '  %s-%s %s\n' "$DIM" "$RST" "$1"; }   # not applicable on this OS
warn()    { printf '  %s!%s %s\n' "$YLW" "$RST" "$1"; }
fail()    { printf '  %sx%s %s\n' "$RED" "$RST" "$1"; FAILURES=$((FAILURES + 1)); }
have()    { command -v "$1" >/dev/null 2>&1; }
confirm() {  # confirm <question> — yes without asking when DOTFILES_YES=1
  [[ "${DOTFILES_YES:-}" == 1 ]] && return 0
  local answer
  read -r -p "  $1 [y/N] " answer
  [[ "$answer" == [yY]* ]]
}
install_or_skip() {  # install_or_skip <bin-name> — returns 0 if install is needed
  if have "$1"; then same "$1"; return 1; fi
  changed "installing $1"
  return 0
}

# ════════════════════════════════════════════════════════════════
# The symlink tables. Add a new dotfile here and nowhere else.
# Format: <path relative to repo>|<absolute target>
# LINKS_ALL applies everywhere ($OS picks the per-OS variant of a shared
# target); LINKS_MAC holds files that only exist on the Mac; LINKS_LAYER
# holds layer files, linked only when their layer is on and the file exists.
# ════════════════════════════════════════════════════════════════
LINKS_ALL=(
  "home/.zshrc|$HOME/.zshrc"
  "home/.zprofile|$HOME/.zprofile"
  "home/.zshenv|$HOME/.zshenv"
  "home/.tmux.conf|$HOME/.tmux.conf"
  "home/.gitconfig|$HOME/.gitconfig"
  "home/.hushlogin|$HOME/.hushlogin"

  "config/tp/tp_tui.py|$HOME/.config/tp/tp_tui.py"
  "config/tmux-resurrect/agents.sh|$HOME/.tmux/plugins/tmux-resurrect/save_command_strategies/agents.sh"

  "claude/CLAUDE.md|$HOME/.claude/CLAUDE.md"
  "claude/os/$OS.md|$HOME/.claude/os.md"
  "claude/settings.json|$HOME/.claude/settings.json"
  "claude/keybindings.json|$HOME/.claude/keybindings.json"
  "claude/init-submodules.sh|$HOME/.claude/init-submodules.sh"
  "claude/skills|$HOME/.claude/skills"
  "claude/skills|$HOME/.copilot/skills"
  "copilot/settings.json|$HOME/.copilot/settings.json"
)

LINKS_MAC=(
  "home/bin/poke_ghostty.sh|$HOME/bin/poke_ghostty.sh"
  "config/ghostty/config|$HOME/Library/Application Support/com.mitchellh.ghostty/config"
  "vscode/settings.json|$HOME/Library/Application Support/Code/User/settings.json"
  "vscode/keybindings.json|$HOME/Library/Application Support/Code/User/keybindings.json"
)

LINKS_LAYER=(
  "personal/gitconfig|$HOME/.gitconfig.local"
  "personal/zshrc|$HOME/.config/zsh/local.zsh"
  "personal/zshenv|$HOME/.config/zsh/local.zshenv"
  "personal/profile.md|$HOME/.claude/profile.md"
  "personal/ssh-config|$HOME/.ssh/config"
  "work/claude.md|$HOME/.claude/work.md"
)

# A layer may also hold a Brewfile (Mac), skills/ and bin/. Set in main().
LAYERS=(personal)

build_links() {
  local entry layer f d name
  LINKS=("${LINKS_ALL[@]}")
  (( IS_MAC )) && LINKS+=("${LINKS_MAC[@]}")
  for entry in "${LINKS_LAYER[@]}"; do
    [[ " ${LAYERS[*]} " == *" ${entry%%/*} "* && -e "$DOTFILES/${entry%%|*}" ]] && LINKS+=("$entry")
  done
  for layer in "${LAYERS[@]}"; do
    for f in "$DOTFILES/$layer"/bin/*; do
      [[ -f "$f" ]] && LINKS+=("$layer/bin/${f##*/}|$HOME/bin/${f##*/}")
    done
  done
  # Codex owns ~/.codex/skills/.system, so link skills one by one, not the whole
  # directory. Codex invokes them as `$name`, not `/name`.
  for d in "$DOTFILES"/claude/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue   # skips synced/ and stray dirs
    name="${d%/}"; name="${name##*/}"
    LINKS+=("claude/skills/$name|$HOME/.codex/skills/$name")
  done
}

# Layer skills join claude/skills/ as symlinks, so the one skills folder still
# serves Claude, Copilot and Codex. A block at the end of .git/info/exclude
# (local to this clone) lists them, rebuilt each run so it never goes stale.
link_layer_skills() {
  local layer d name dst exclude="$DOTFILES/.git/info/exclude" mark="# dotfiles: layer skills"
  for layer in "${LAYERS[@]}"; do
    for d in "$DOTFILES/$layer"/skills/*/; do
      [[ -f "$d/SKILL.md" || -d "$d/.claude-plugin" ]] || continue
      d="${d%/}"; name="${d##*/}"; dst="$DOTFILES/claude/skills/$name"
      if [[ -L "$dst" && "$(readlink "$dst")" == "$d" ]]; then
        same "skill $name"
      elif [[ -e "$dst" || -L "$dst" ]]; then
        fail "skill $name: claude/skills/$name already exists"
      else
        ln -s "$d" "$dst" && changed "skill $name"
      fi
    done
  done
  [[ -f "$exclude" ]] || return 0
  { sed "/^$mark\$/,\$d" "$exclude"; echo "$mark"
    for dst in "$DOTFILES"/claude/skills/*; do [[ -L "$dst" ]] && echo "claude/skills/${dst##*/}"; done
  } > "$exclude.new" && mv "$exclude.new" "$exclude"
}

prune_dangling() {  # prune_dangling <dir> — remove broken links into this repo
  local l
  for l in "$1"/* "$1"/.[!.]*; do
    [[ -L "$l" && ! -e "$l" && "$(readlink "$l")" == "$DOTFILES/"* ]] || continue
    rm "$l" && changed "removed stale ${l/#$HOME/~}"
  done
}

# ════════════════════════════════════════════════════════════════
# stage: brew
# ════════════════════════════════════════════════════════════════
bundle_check_and_install() {  # bundle_check_and_install <label> <Brewfile path>
  local label="$1" file="$2"
  if brew bundle check --file="$file" >/dev/null 2>&1; then
    same "$label satisfied"
    return 0
  fi
  changed "brew bundle install $label (this takes a while on a fresh machine)"
  brew bundle install --file="$file" || fail "brew bundle had failures ($label)"
}

stage_brew() {
  stage "brew"

  if (( IS_MAC )) && ! xcode-select -p >/dev/null 2>&1; then
    changed "installing Xcode Command Line Tools (a GUI dialog will open)"
    xcode-select --install
    warn "finish the CLT dialog, then re-run: ./install.sh brew"
    return 0
  fi

  if ! have brew; then
    changed "installing Homebrew to $BREW_PREFIX"
    # Linux: NONINTERACTIVE skips the RETURN prompt; linux/setup.sh has already
    # created $BREW_PREFIX owned by us, so the installer never reaches for sudo.
    (( IS_MAC )) || export NONINTERACTIVE=1
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
      || { fail "Homebrew install failed"; return 1; }
    eval "$("$BREW_PREFIX/bin/brew" shellenv)"
    (( IS_MAC )) || brew analytics off >/dev/null 2>&1
  fi

  bundle_check_and_install "$BREWFILE" "$DOTFILES/$BREWFILE"

  local layer
  for layer in "${LAYERS[@]}"; do
    [[ -f "$DOTFILES/$layer/Brewfile" ]] || continue
    if (( IS_MAC )); then
      bundle_check_and_install "$layer/Brewfile" "$DOTFILES/$layer/Brewfile"
    else
      skip "$layer/Brewfile (Mac only: casks)"
    fi
  done
}

# ════════════════════════════════════════════════════════════════
# stage: shell — oh-my-zsh, the one custom plugin, and TPM
# ════════════════════════════════════════════════════════════════
stage_shell() {
  stage "shell"

  have zsh || { fail "zsh is not installed (Linux: run linux/setup.sh first)"; return 1; }

  if [[ -d "$HOME/.oh-my-zsh" ]]; then
    same "oh-my-zsh"
  else
    changed "installing oh-my-zsh"
    # --unattended so it neither runs zsh nor overwrites the .zshrc we ship.
    RUNZSH=no KEEP_ZSHRC=yes sh -c \
      "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended \
      || fail "oh-my-zsh install failed"
  fi

  # .zshrc's plugins=(... zsh-autosuggestions ...) needs this clone to exist,
  # otherwise every new shell prints a "plugin not found" warning.
  local zsa="$HOME/.oh-my-zsh/custom/plugins/zsh-autosuggestions"
  if [[ -d "$zsa" ]]; then
    same "zsh-autosuggestions"
  else
    changed "cloning zsh-autosuggestions"
    git clone -q https://github.com/zsh-users/zsh-autosuggestions "$zsa" \
      || fail "zsh-autosuggestions clone failed"
  fi

  # .tmux.conf's last line runs TPM; without the clone tmux prints an error
  # on every session start. Plugins are cloned here, not by TPM's prefix+I.
  local p
  for p in tpm tmux-resurrect tmux-continuum; do
    if [[ -d "$HOME/.tmux/plugins/$p" ]]; then
      same "$p"
    else
      changed "cloning $p"
      git clone -q "https://github.com/tmux-plugins/$p" "$HOME/.tmux/plugins/$p" \
        || fail "$p clone failed"
    fi
  done
}

# ════════════════════════════════════════════════════════════════
# stage: link
# ════════════════════════════════════════════════════════════════
backup() {  # backup <path> — move it under BACKUP_DIR, keeping its shape
  local target="$1" rel dest
  rel="${target#"$HOME"/}"
  dest="$BACKUP_DIR/$rel"
  mkdir -p "$(dirname "$dest")"
  mv "$target" "$dest"
}

stage_link() {
  stage "link"
  local entry src dst abs_src dir

  # A removed skill or layer file leaves a dangling link behind. Skills first:
  # their Codex links only dangle once the skill link is gone.
  for dir in "$DOTFILES/claude/skills" "$HOME/.codex/skills" "$HOME/bin" \
             "$HOME/.config/zsh" "$HOME/.claude" "$HOME"; do
    prune_dangling "$dir"
  done
  link_layer_skills
  build_links

  for entry in "${LINKS[@]}"; do
    src="${entry%%|*}"
    dst="${entry#*|}"
    abs_src="$DOTFILES/$src"

    if [[ ! -e "$abs_src" ]]; then
      fail "missing in repo: $src"
      continue
    fi

    if [[ -L "$dst" ]] && [[ "$(readlink "$dst")" == "$abs_src" ]]; then
      same "${dst/#$HOME/~}"
      continue
    fi

    mkdir -p "$(dirname "$dst")"
    if [[ -e "$dst" || -L "$dst" ]]; then
      backup "$dst"
      changed "${dst/#$HOME/~}  (previous version backed up)"
    else
      changed "${dst/#$HOME/~}"
    fi
    ln -s "$abs_src" "$dst" || fail "could not link $dst"
  done

  [[ -d "$BACKUP_DIR" ]] && warn "backups: ${BACKUP_DIR/#$HOME/~}"
  return 0
}

# ════════════════════════════════════════════════════════════════
# stage: macos
# ════════════════════════════════════════════════════════════════
set_default() {  # set_default <domain> <key> <type> <value>
  local domain="$1" key="$2" type="$3" value="$4" expected="$4" current
  [[ "$type" == "bool" ]] && { [[ "$value" == "true" ]] && expected=1 || expected=0; }
  current="$(defaults read "$domain" "$key" 2>/dev/null)"
  if [[ "$current" == "$expected" ]]; then
    same "$domain $key = $current"
    return 0
  fi
  if defaults write "$domain" "$key" "-$type" "$value" 2>/dev/null; then
    changed "$domain $key: ${current:-unset} -> $expected"
  else
    warn "could not write $domain $key (System Settings may own it)"
  fi
}

set_app_shortcut() {  # set_app_shortcut <domain> <menu title> <keys: @=cmd ~=opt ^=ctrl $=shift>
  local domain="$1" title="$2" keys="$3" before after
  before="$(defaults read "$domain" NSUserKeyEquivalents 2>/dev/null)"
  if ! defaults write "$domain" NSUserKeyEquivalents -dict-add "$title" "$keys" 2>/dev/null; then
    warn "could not set $domain shortcut: $title"
    return 0
  fi
  after="$(defaults read "$domain" NSUserKeyEquivalents 2>/dev/null)"
  if [[ "$before" == "$after" ]]; then same "$domain shortcut: $title"; else changed "$domain shortcut: $title"; fi
}

stage_macos() {
  stage "macos"
  local before=$CHANGES

  confirm "Set key repeat, autocorrect off, Dock, Finder and Chrome tab keys?" \
    || { skip "macOS settings (declined)"; return 0; }

  # Keyboard: fastest repeat, shortest delay. The single most-felt setting.
  set_default -g KeyRepeat int 2
  set_default -g InitialKeyRepeat int 15

  # No autocorrect anywhere — it mangles code and CLI text.
  set_default -g NSAutomaticCapitalizationEnabled bool false
  set_default -g NSAutomaticSpellingCorrectionEnabled bool false
  set_default -g NSAutomaticPeriodSubstitutionEnabled bool false

  set_default com.apple.universalaccess reduceMotion bool true

  # Spaces must keep a fixed order — muscle memory for ctrl+<n> depends on it.
  set_default com.apple.dock mru-spaces bool false
  set_default com.apple.dock show-recents bool false
  set_default com.apple.dock autohide bool false
  set_default com.apple.dock tilesize int 49

  set_default com.apple.finder FXPreferredViewStyle string Nlsv

  if (( CHANGES > before )); then
    killall Dock Finder 2>/dev/null
    warn "some settings apply only after logout (see MANUAL.md)"
  fi

  # Chrome: opt+cmd+up/down switch tabs (suits vertical tabs). Titles must match Chrome's Tab menu.
  before=$CHANGES
  set_app_shortcut com.google.Chrome "Select Previous Tab" '@~\Uf700'
  set_app_shortcut com.google.Chrome "Select Next Tab" '@~\Uf701'
  (( CHANGES > before )) && warn "restart Chrome (cmd+Q) to pick up its shortcuts"
  return 0
}

# ════════════════════════════════════════════════════════════════
# stage: agents
# ════════════════════════════════════════════════════════════════
ensure_bin() {  # ensure_bin <bin> <label> <install command...>
  local bin="$1" label="$2"; shift 2
  install_or_skip "$bin" || return 0
  "$@" >/dev/null 2>&1 || fail "$label failed"
}

stage_agents() {
  stage "agents"

  ensure_bin claude   "claude install" bash -c 'curl -fsSL https://claude.ai/install.sh | bash'

  # On the Mac codex comes from its cask instead, see below.
  (( IS_MAC )) || ensure_bin codex "npm i -g @openai/codex" npm i -g @openai/codex
  (( WITH_WORK )) && ensure_bin workiq "npm i -g @microsoft/workiq" npm i -g @microsoft/workiq

  if (( IS_MAC )); then
    # `copilot` comes from the copilot-cli cask in the Brewfile.
    have copilot && same "copilot" || warn "copilot missing — run ./install.sh brew"

    # codex comes from the codex cask in the Brewfile (see stage_brew) — npm's
    # @openai/codex fetches its native binary on first run, which
    # Gatekeeper/XProtect has blocked as malware.
    have codex && same "codex" || warn "codex missing — run ./install.sh brew"
  else
    # Linux: GitHub's installer for copilot; codex came from npm above (no Gatekeeper).
    ensure_bin copilot "copilot install" bash -c 'curl -fsSL https://gh.io/copilot-install | bash'
  fi
}

# ════════════════════════════════════════════════════════════════
# stage: vscode
# ════════════════════════════════════════════════════════════════
stage_vscode() {
  stage "vscode"
  if ! have code; then
    warn "the \`code\` CLI is not on PATH — open VS Code and run"
    warn "  Shell Command: Install 'code' command in PATH"
    return 0
  fi
  local installed ext
  installed="$(code --list-extensions 2>/dev/null)"
  while read -r ext; do
    [[ -z "$ext" ]] && continue
    if grep -qxF "$ext" <<<"$installed"; then
      same "$ext"
    else
      changed "$ext"
      code --install-extension "$ext" >/dev/null 2>&1 || fail "could not install $ext"
    fi
  done < "$DOTFILES/vscode/extensions.txt"
}

# ════════════════════════════════════════════════════════════════
# stage: python
# ════════════════════════════════════════════════════════════════
stage_python() {
  stage "python"

  # ~/miniforge3, not the Homebrew cask: home/.zshrc's conda block points at
  # $HOME/miniforge3, and the cask installs somewhere else entirely.
  if [[ -d "$HOME/miniforge3" ]]; then
    same "miniforge3"
  else
    changed "installing Miniforge3 to ~/miniforge3"
    local url
    url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$MINIFORGE_OS-$(uname -m).sh"
    curl -fsSL "$url" -o /tmp/miniforge.sh \
      && bash /tmp/miniforge.sh -b -p "$HOME/miniforge3" \
      || { fail "miniforge install failed"; return 1; }
    rm -f /tmp/miniforge.sh
    # No `conda init` — home/.zshrc already carries the init block, and
    # conda init would rewrite it with absolute paths through the symlink.
  fi

  # The Mac's base env is this curated list, so keep it in sync. A Linux box
  # usually has its own base env this list would fight; leave it alone there.
  if (( IS_MAC )); then
    changed "updating base env from environments/base.yml"
    "$HOME/miniforge3/bin/mamba" env update -n base -f "$DOTFILES/environments/base.yml" \
      || fail "base env update failed"
  else
    skip "base env update (Mac state)"
  fi
}

# ════════════════════════════════════════════════════════════════
# stage: rust — rustup/cargo and bun via their own installers.
#
# Both have Homebrew formulae too, but brew's versions replace each tool's
# own self-updater (`rustup update`, `bun upgrade`) with brew-managed
# versioning — a behavior change, not just a different install path — so
# this stage deliberately stays outside the Brewfile mechanism.
# ════════════════════════════════════════════════════════════════
stage_rust() {
  stage "rust"
  local -a pids=()

  if install_or_skip rustup; then
    ( curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y ) &
    pids+=("rustup:$!")
  fi

  if install_or_skip bun; then
    ( curl -fsSL https://bun.sh/install | bash ) &
    pids+=("bun:$!")
  fi

  # Both installers are independent network downloads — run them concurrently
  # instead of waiting on one before starting the other.
  local entry name pid
  for entry in ${pids[@]+"${pids[@]}"}; do
    name="${entry%%:*}" pid="${entry#*:}"
    wait "$pid" || fail "$name install failed"
  done
}

# ════════════════════════════════════════════════════════════════
# stage: secrets
# ════════════════════════════════════════════════════════════════
stage_secrets() {
  stage "secrets"

  # ~/.ssh/config is a link to personal/ssh-config (the `link` stage), so
  # edits made through it, by you or by OrbStack, land in personal/.
  # ── macOS text replacements ───────────────────────────────────
  local env_file="$DOTFILES/personal/secrets.env"
  if [[ ! -f "$env_file" ]]; then
    skip "personal/secrets.env absent (see personal.example/README.md)"
    return 0
  fi

  # Build the NSUserDictionaryReplacementItems array from key=value lines.
  local plist="(" key value line
  local n=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    plist+="{on=1;replace=\">$key\";with=\"${value//\"/\\\"}\";},"
    n=$((n + 1))
  done < "$env_file"
  plist+=")"

  # Compare against what's already set, so re-running is a genuine no-op
  # instead of a spurious "changed" every time.
  if python3 - "$env_file" <<'PY'
import plistlib, subprocess, sys
want = {}
for line in open(sys.argv[1]):
    line = line.rstrip("\n")
    if not line or line.startswith("#"):
        continue
    k, _, v = line.partition("=")
    want[k] = v
out = subprocess.run(["defaults", "export", "-g", "-"], capture_output=True).stdout
have = {str(i.get("replace", "")).lstrip(">"): str(i.get("with", ""))
        for i in plistlib.loads(out).get("NSUserDictionaryReplacementItems", [])}
sys.exit(0 if have == want else 1)
PY
  then
    same "text replacements ($n shortcuts)"
    return 0
  fi

  if defaults write -g NSUserDictionaryReplacementItems "$plist" 2>/dev/null; then
    changed "text replacements ($n shortcuts)"
    warn "text replacements need a logout to take effect"
  else
    fail "could not write text replacements"
  fi
}

# ════════════════════════════════════════════════════════════════
# doctor — verify, change nothing
# ════════════════════════════════════════════════════════════════
doctor_check_bundle() {  # doctor_check_bundle <label> <Brewfile path>
  local label="$1" file="$2" unsat
  # --verbose reports on stderr, not stdout. Redirecting it to /dev/null
  # makes this check silently pass, which is worse than not having it.
  unsat="$(brew bundle check --file="$file" --verbose 2>&1 | grep -c '^→')"
  if (( unsat == 0 )); then
    same "$label satisfied"
  else
    # Casks you installed by dragging the .app in are invisible to brew and
    # will show here forever. `brew install --cask --adopt <name>` hands one
    # over to brew; until then this line is noise, not a fault.
    warn "$unsat $label entries unsatisfied — ./install.sh brew (apps you installed by hand: brew install --cask --adopt <name>)"
  fi
}

run_doctor() {
  stage "doctor"
  local entry src dst abs_src problems=0

  for entry in "${LINKS[@]}"; do
    src="${entry%%|*}"; dst="${entry#*|}"; abs_src="$DOTFILES/$src"
    if [[ ! -e "$abs_src" ]]; then
      fail "missing in repo: $src"; problems=$((problems + 1))
    elif [[ ! -e "$dst" && ! -L "$dst" ]]; then
      fail "not installed: ${dst/#$HOME/~}"; problems=$((problems + 1))
    elif [[ ! -L "$dst" ]]; then
      # An app replaced the symlink with a real file. `./install.sh pull`
      # folds those edits back into the repo so you can commit them.
      fail "DRIFT (real file, not a link): ${dst/#$HOME/~}"; problems=$((problems + 1))
    elif [[ "$(readlink "$dst")" != "$abs_src" ]]; then
      fail "links elsewhere: ${dst/#$HOME/~} -> $(readlink "$dst")"; problems=$((problems + 1))
    else
      same "${dst/#$HOME/~}"
    fi
  done

  if have brew; then
    doctor_check_bundle "$BREWFILE" "$DOTFILES/$BREWFILE"
    local layer
    for layer in "${LAYERS[@]}"; do
      (( IS_MAC )) && [[ -f "$DOTFILES/$layer/Brewfile" ]] && doctor_check_bundle "$layer/Brewfile" "$DOTFILES/$layer/Brewfile"
    done
  fi

  # Only link problems count as failures. A warning above is still a warning.
  (( problems == 0 )) && printf '\n%sdoctor: every link clear%s\n' "$GRN" "$RST"
  return 0
}

# ════════════════════════════════════════════════════════════════
# pull — fold app-rewritten files back into the repo
# ════════════════════════════════════════════════════════════════
run_pull() {
  stage "pull"
  local entry src dst abs_src
  for entry in "${LINKS[@]}"; do
    src="${entry%%|*}"; dst="${entry#*|}"; abs_src="$DOTFILES/$src"
    if [[ -e "$dst" && ! -L "$dst" ]]; then
      if [[ -d "$dst" ]]; then
        rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' "$dst/" "$abs_src/"
      else
        cp "$dst" "$abs_src"
      fi
      changed "pulled $src"
    fi
  done
  (( CHANGES == 0 )) && same "nothing had drifted"
  printf '\n%s\n' "Review with: git -C '$DOTFILES' diff"
  return 0
}

# ════════════════════════════════════════════════════════════════
# main
# ════════════════════════════════════════════════════════════════
main() {
  local -a args=() stages
  local a
  for a in "$@"; do
    case "$a" in
      --with-work) WITH_WORK=1 ;;
      *)           args+=("$a") ;;
    esac
  done

  # A machine linked once with --with-work stays a work machine: the
  # ~/.claude/work.md link marks it.
  [[ -L "$HOME/.claude/work.md" ]] && WITH_WORK=1
  (( WITH_WORK )) && LAYERS+=(work)
  [[ "${args[0]:-}" == doctor || "${args[0]:-}" == pull ]] && build_links

  case "${args[0]:-}" in
    doctor) run_doctor; exit $(( FAILURES > 0 )) ;;
    pull)   run_pull;   exit $(( FAILURES > 0 )) ;;
    "")     stages=("${ALL_STAGES[@]}") ;;
    *)      stages=("${args[@]}") ;;
  esac

  printf '%sdotfiles%s  %s  (%s)\n' "$B" "$RST" "$DOTFILES" "$OS"

  if [[ ! -d "$DOTFILES/personal" ]]; then
    stage "personal"
    cp -R "$DOTFILES/personal.example" "$DOTFILES/personal"
    changed "personal/  (copied from personal.example/)"
    warn "edit personal/gitconfig and personal/profile.md, then re-run"
  fi

  local s
  for s in "${stages[@]}"; do
    if [[ " ${ALL_STAGES[*]} " == *" $s "* ]]; then
      "stage_$s"
    else
      fail "unknown stage on $OS: $s (valid: ${ALL_STAGES[*]} doctor pull)"
    fi
  done

  printf '\n%s%d change(s), %d failure(s)%s\n' "$B" "$CHANGES" "$FAILURES" "$RST"
  if (( FAILURES > 0 )); then
    printf '%sSomething above failed. Nothing was silently skipped — read the x lines.%s\n' "$RED" "$RST"
    exit 1
  fi
  printf 'Next: work through %sMANUAL.md%s — the parts no script can do.\n' "$B" "$RST"
}

main "$@"
