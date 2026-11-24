# This OS: Linux

A headless box reached over SSH: no clipboard, no `caffeinate`, no `open`; nothing sleeps.

You can use my Mac as `mac`: `~/bin/rsh mac '<command>'` runs a command there; `rsync mac:<path> .` pulls files.
When you finish a file I need to look at, send it with `~/bin/vsend <path>…`, then `~/bin/rsh mac 'open -g <the Mac path it prints>'` (call `~/bin` tools by full path: `/usr/bin/rsh` is a different tool).
Reach another VM through the Mac: `~/bin/rsh mac/<host> '<command>'`, and copy with `~/bin/rsh mac vcp <this-host>:<path> <host>:<dir>`.
The Mac is my laptop: do not change its settings or delete files there unless I ask.
If `ssh mac` fails, end with one line I can paste on my Mac instead:
`vcp <ssh-host>:<absolute path> ~/Downloads && open ~/Downloads/<file name>`. Take the host from `~/.claude/local.md`; if it names none, use `hostname -s`.

## Tools

Homebrew at `/home/linuxbrew/.linuxbrew` for CLI tools; system packages via apt. Anything specific to this particular machine (storage layout, GPUs, cloud-agent quirks) is in `~/.claude/local.md` if it exists — read it before touching disks or drivers.
