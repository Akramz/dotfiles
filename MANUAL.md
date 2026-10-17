# Manual steps

Everything `install.sh` cannot do. Work top to bottom. Your own extra steps go
in `personal/MANUAL.md`.

## 1. Before `install.sh`

- [ ] Sign in to your password manager (the web app is fine). Later steps need it.
- [ ] Sign in to iCloud if you want text replacements and Safari to come across on their own.

## 2. Accounts and CLIs

- [ ] `gh auth login`, once per GitHub account. `gh auth switch` moves between them.
- [ ] `az login`
- [ ] `gcloud auth login`
- [ ] `aws configure`, or skip it and use `--no-sign-request` for public buckets.
- [ ] Sign in to Claude Code (`claude`), Codex (`codex`) and Copilot (`copilot`).

## 3. System Settings

No reliable `defaults` key exists for these. Click them.

- [ ] **Notifications**: turn them off for every app you don't need to hear from.
- [ ] **Appearance**: *Auto* (follows light and dark).
- [ ] **Keyboard → Text Input → Input Sources**: remove the ones you don't use.
- [ ] **Keyboard → Keyboard Shortcuts → Spotlight**: uncheck ⌘Space, so Raycast can take it.
- [ ] **Desktop & Dock**: confirm *Automatically rearrange Spaces* is off. `install.sh macos` sets it, but a macOS update can turn it back on.

If you said yes to `install.sh macos`, it already set: key repeat rate and
delay, reduce motion, autocorrect, autocapitalise and period substitution off,
Dock recents, autohide and size, Finder list view, and Chrome's
opt+cmd+up/down tab keys. Some of these need a logout.

## 4. Permissions

macOS will not grant these from a script. Grant them on first launch, or in
**Privacy & Security**:

- [ ] **Accessibility**: Ghostty (its global ctrl+space needs it), Raycast, superwhisper, KeyCastr
- [ ] **Input Monitoring**: superwhisper, KeyCastr
- [ ] **Screen Recording**: Kap
- [ ] **Full Disk Access**: Ghostty, VS Code (agents read across the disk)

## 5. App configuration

- [ ] **Raycast**: bind it to ⌘Space.
- [ ] **superwhisper**: set the dictation hotkey and download a model (none ship with it).
- [ ] **Ghostty**: nothing to do. It opens *no* window on launch; press ctrl+space. If the hotkey dies (macOS disables Ghostty's event tap after a timeout), run `poke-ghostty` instead of relaunching.
- [ ] **Chrome**: quit and reopen it (cmd+Q) to pick up the tab shortcuts.
- [ ] **VS Code**: if `install.sh vscode` warned about the `code` CLI, run *Shell Command: Install 'code' command in PATH* from the command palette, then `./install.sh vscode`.

## 6. Secrets and tokens

- [ ] Restore `personal/secrets.env`, `personal/ssh-config` and your SSH keys: [`personal.example/README.md`](personal.example/README.md#secrets-from-a-password-manager). Text replacements need a logout.
- [ ] `/weekly-work-summary`: save your Toggl API token (Toggl → Profile settings → API Token) to `~/.config/toggl/token`.
- [ ] `gog` skill (agents read your Google mail, calendar and files):
  1. Create a Google OAuth desktop client (`gog auth setup --help`). Fill Branding's homepage and privacy policy URLs (any public URL works) and press **Publish app** under Audience, or tokens expire after 7 days.
  2. `gog auth credentials set <client.json>`
  3. `gog auth add <email> --services gmail,calendar,drive,docs,sheets,contacts`
  4. `gog auth alias set personal <email>`. The skill reads the `personal` alias.

## 7. Work machine (`--with-work`)

`./install.sh --with-work` (or `./install.sh brew --with-work`) adds
`work/Brewfile`: Edge, Teams, Office, Azure Storage Explorer and `azure-cli`.
The rest comes from your company once you enrol:

- [ ] **Company Portal**: enrol. It pushes the managed apps.
- [ ] **Azure VPN Client** (App Store).
- [ ] If PyPI is blocked, set your company's approved package proxy as the default index in `~/.config/uv/uv.toml` (`[[index]]` with `default = true`). The agents read `~/.claude/work.md`, which points there.
- [ ] `~/.npmrc` points npm at your company's internal registry. It is not in this repo; it comes back with the corporate tooling.
- [ ] **Work IQ**: `workiq accept-eula && workiq auth login`. Agents use it through the `workiq` skill.

## 8. Verify

- [ ] `./install.sh doctor` → `every link clear`
- [ ] ctrl+space opens Ghostty; `tp` lists sessions; `cld test` starts a Claude session in the current checkout.
- [ ] `claude` → `/skills` lists the repo skills.

## 9. Linux

After `linux/setup.sh` (which ends by running `./install.sh`):

- [ ] The §2 sign-ins and the §6 `gog` step. On a headless box, first run `gog auth keyring file`, put `GOG_KEYRING_PASSWORD` in `personal/zshenv`, and add `--manual` to `gog auth add`.
- [ ] Open a new SSH session. It should land in zsh with the `host:~ %` prompt.
- [ ] `claude` → `/memory` lists `~/.claude/CLAUDE.md` and the `os.md` import; `/skills` lists the repo skills.
- [ ] `tmux -V` is 3.3 or newer (brew's), so shift+enter works inside agent TUIs.
- [ ] Notes about that particular machine (storage, GPUs, quirks) go in `personal/` or `~/.claude/local.md`, not in the repo.

## Install commands that may break

These are the lines in `install.sh` most likely to need a fix on a fresh machine:

- Codex comes from the `codex` cask on the Mac, not `npm i -g @openai/codex`. The npm package downloads its native binary on first run, and Gatekeeper/XProtect has blocked that download as malware before.
- `claude`, rustup and bun install through their vendors' curl-pipe-bash scripts. If a URL moves, the stage fails loudly.
- Linux: the agent installers are in `stage_agents`; slow-but-fine Homebrew bootstrap notes are in `Brewfile.linux`'s header.
