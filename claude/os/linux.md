# This OS: Linux

A headless box reached over SSH: no clipboard, no `caffeinate`, no `open`; nothing sleeps.

When you finish a file I need to look at, or I ask for files on my Mac, send them with `vsend <path>…`
and give the Mac path it prints. If vsend finds no tunnel, end with one line I can paste on my Mac instead:
`vcp <ssh-host>:<absolute path> ~/Downloads && open ~/Downloads/<file name>`. Take the host from `~/.claude/local.md`; if it names none, use `hostname -s`.
Data for another VM goes through the Mac: give me the `vcp <this-host>:<path> <other-host>:<dir>` line to run.

## Tools

Homebrew at `/home/linuxbrew/.linuxbrew` for CLI tools; system packages via apt. Anything specific to this particular machine (storage layout, GPUs, cloud-agent quirks) is in `~/.claude/local.md` if it exists — read it before touching disks or drivers.
