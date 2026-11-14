# This OS: Linux

A headless box reached over SSH: no clipboard, no `caffeinate`, no `open`; nothing sleeps.

When you finish a file I need to look at, end with one line I can paste on my Mac:
`vopen <ssh-host>:<absolute path>`. Take the host from `~/.claude/local.md`; if it names none, use `hostname -s`.

## Tools

Homebrew at `/home/linuxbrew/.linuxbrew` for CLI tools; system packages via apt. Anything specific to this particular machine (storage layout, GPUs, cloud-agent quirks) is in `~/.claude/local.md` if it exists — read it before touching disks or drivers.
