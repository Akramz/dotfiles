---
name: what-else
description: Suggest the top 3 priority tasks that don't collide with parallel agents. Use when the user runs /what-else.
---

# What Else

Read `ROADMAP.md` and `PROGRESS.md` in the current project. Figure out what
other coding agents are doing in parallel right now (check `ListAgents`,
other git branches/worktrees, and anything PROGRESS.md says is in flight).

Then suggest the top 3 tasks from the roadmap that:
- Are not already done (per PROGRESS.md)
- Don't touch the same files/areas the parallel agents are working on

Keep the output short: a numbered list of 3 tasks, one line each, with a
one-line reason why each is safe to start now. Don't start the work — just
suggest it.
