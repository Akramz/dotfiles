# personal/

Everything that is yours, not the repo's. The first `./install.sh` copies this
folder to `personal/`, which is gitignored. Edit the copies, then run
`./install.sh` again.

| File | Where it goes | What to put in it |
|---|---|---|
| `gitconfig` | linked to `~/.gitconfig.local` | `[user]` name and email; `safe.directory`, extra credential helpers |
| `profile.md` | linked to `~/.claude/profile.md` | who you are, your GitHub accounts, where your repos live. `claude/CLAUDE.md` imports it, so every agent session starts with it |
| `zshrc` | linked to `~/.config/zsh/local.zsh` | your aliases and functions; `~/.zshrc` sources it last |
| `zshenv` | linked to `~/.config/zsh/local.zshenv` | environment for every shell. `export DOTFILES_YES=1` makes `install.sh` stop asking |
| `Brewfile` | read by the `brew` stage | your own apps (Mac only) |
| `bin/<script>` | linked to `~/bin/<script>` | your own scripts |
| `skills/<name>/` | symlinked into `claude/skills/<name>` | private skills; Claude, Copilot and Codex all see them. `.git/info/exclude` keeps them out of the repo's `git status` |
| `secrets.env` | macOS text replacements | `key=value` lines; typing `>key` anywhere expands to the value. Shape: `secrets.example.env` |
| `ssh-config` | linked to `~/.ssh/config` | your ssh hosts; keep it mode 600. Shape: `ssh-config.example` |

`install.sh` links only the files you have. Delete what you don't need.
`ssh-config` takes effect with `./install.sh link`, `secrets.env` with `./install.sh secrets`; text
replacements need a logout. `personal/MANUAL.md` is a good place for your own
setup steps.

## Keep it in git

`personal/` can be its own private repo. Its `.gitignore` already keeps the
secrets out, even there:

```sh
cd personal
git init && git add . && git commit -m "personal"
git remote add origin <your private repo> && git push -u origin main
```

On a new machine, clone it to `personal/` before the first `./install.sh`.

## Secrets from a password manager

`secrets.env`, `ssh-config` and your SSH private keys live in your password
manager, never in git. One secure note per file, keys as attachments:

| Restore | To | From |
|---|---|---|
| Text replacements | `personal/secrets.env` | a secure note, pasted |
| SSH config | `personal/ssh-config` | a secure note, pasted |
| SSH private keys | `~/.ssh/` | attachments |

Then:

```sh
./install.sh secrets
chmod 600 ~/.ssh/<each key>     # ssh refuses keys others can read
```

## Not here on purpose

- **GitHub tokens**: `gh auth login` stores them in the keychain.
- **Cloud credentials**: `az login`, `gcloud auth login`, `aws configure`. All interactive.
- **Skill tokens**: the Toggl token and the Google OAuth client; see MANUAL.md §6.
- **`~/.npmrc`** on a work machine: it comes from the corporate tooling.
