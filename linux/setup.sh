#!/usr/bin/env bash
#
# linux/setup.sh — the root-level prerequisites ./install.sh cannot do itself
# on a Debian/Ubuntu machine, then ./install.sh with the same arguments.
#
# Generic on purpose: nothing here knows about a particular box. Machine-local
# work (drivers, mounts, cloud-agent quirks) belongs in an untracked script that
# runs first and then calls this one — see README, "Linux".
#
# Runs as your user and uses sudo per command: Homebrew must be user-owned.
# Idempotent, so `linux/setup.sh doctor` is "ensure prerequisites, then doctor".
set -uo pipefail

DOTFILES="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
BREW_PREFIX=/home/linuxbrew/.linuxbrew
PKGS=(zsh build-essential procps curl file git)   # login shell + Homebrew's documented prerequisites

sudo -n true 2>/dev/null || { echo "passwordless sudo required"; exit 1; }

# One dpkg-query for all of them; unknown/uninstalled packages simply don't print "installed".
mapfile -t installed < <(dpkg-query -W -f='${Package} ${db:Status-Status}\n' "${PKGS[@]}" 2>/dev/null | awk '$2 == "installed" { print $1 }')
missing=()
for p in "${PKGS[@]}"; do [[ " ${installed[*]} " == *" $p "* ]] || missing+=("$p"); done
(( ${#missing[@]} )) && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${missing[@]}"

# The login shell. Some managed images reset this at boot; if yours does, hand
# off from ~/.bashrc instead (machine-local, not in this repo).
[[ "$(getent passwd "$USER" | cut -d: -f7)" == */zsh ]] || sudo chsh -s "$(command -v zsh)" "$USER"

# A user-owned prefix lets Homebrew's installer run without sudo.
[[ -d "$BREW_PREFIX" && -O "$BREW_PREFIX" ]] || sudo install -d -o "$USER" -g "$USER" "$BREW_PREFIX"

exec "$DOTFILES/install.sh" "$@"
