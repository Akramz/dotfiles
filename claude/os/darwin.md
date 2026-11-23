# This OS: macOS (Apple Silicon)

## Tools

Homebrew at `/opt/homebrew`. Docker via OrbStack.

## Opening apps and files

Don't steal screen focus. Use `open -g` to open files, URLs, and apps.

When you finish something I need to look at (an HTML page, PDF, figure, deck, or a PR or doc URL),
open it with `open -g` without being asked, and give its path or URL in one line.

## SSH hosts

`vcp` (in `~/.zshrc`) copies files or folders between the Mac and a host, or from one host to
another: `vcp hostA:<path> hostB:<dir>`. Files that agents on hosts send with `vsend` land in `~/vm-inbox/<host>/`.
