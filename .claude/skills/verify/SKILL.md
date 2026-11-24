---
name: verify
description: Check that the dotfiles still install and work, not only that they lint. Use before you call a change done, and when asked to verify.
---

# Verify

1. Run `./verify.sh`. It lints (shellcheck, ruff, JSON), links everything into a throwaway
   `$HOME`, checks that a second run changes nothing, and runs `doctor` there. Under 30 s.
2. Run `./install.sh doctor` on this machine. Every `x` line is a real fault; fix it or
   report it. `!` lines are warnings.
3. If you changed a feature (a script in `home/bin`, `tp`, a hook, a pi extension), run it
   once the way the README says and report what you saw.
4. CI runs `./verify.sh` on macOS and Ubuntu on every push.
