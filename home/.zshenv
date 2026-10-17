typeset -U path   # no duplicate PATH entries when shells nest

# uv tools, and the other ~/.local/bin installers (claude, copilot)
export PATH="$HOME/.local/bin:$PATH"
[[ -f "$HOME/.cargo/env" ]] && . "$HOME/.cargo/env"

# Linux: npm globals under $HOME (the system prefix is root-owned on most images).
[[ $OSTYPE == linux* ]] && export NPM_CONFIG_PREFIX="$HOME/.npm-global" PATH="$HOME/.npm-global/bin:$PATH"

# Your personal/zshenv, linked here by install.sh (CUDA paths, cache dirs, cloud settings).
[[ -f "$HOME/.config/zsh/local.zshenv" ]] && source "$HOME/.config/zsh/local.zshenv"
