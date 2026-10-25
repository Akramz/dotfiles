---
name: backlog
description: Save an idea to the user's backlog repo, in the right category folder, then commit and push. Use when the user runs /backlog <idea> or asks to add an idea to their backlog.
---

# Backlog

Take `BACKLOG` (`owner/repo`) and `DEST` from your profile (`~/.claude/profile.md`). The clone is `$DEST/<repo>`. If it is missing, `gh repo clone` it there.

1. `git pull --rebase --autostash` in the clone.
2. Read the categories in the clone's `README.md`. Pick the one that fits the idea best. If none fits, ask.
3. Write `<category>/<snake_case_name>.md`: a short `# Title`, then the user's words as a `>` quote. Add nothing else.
4. Stage that file only. Commit `Add idea: <Title>`. Push to `main`.

Reply in one line: the path, the commit, and any other category or existing idea that is close.
