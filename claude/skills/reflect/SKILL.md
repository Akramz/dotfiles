---
name: reflect
description: Reflect on a period (a week, month, quarter, year or date range) from the user's git commits, Obsidian journal and Toggl time, then suggest improvements against their yearly vision. Use when the user runs /reflect or asks what they did over a period and how to do better.
---

# Reflect

## 1. Gather

```
python3 <this skill's folder>/gather.py PERIOD
```

`PERIOD` is a vault period (`2026`, `2026-Q3`, `2026-Q4-W02`) or two dates (`START END`, both
inclusive). Vault quarters and weeks follow the journal folders, not the calendar, so pass
them as labels. With no period, use this week, Monday to Sunday.

It prints Toggl hours, the user's commits and the vault files for the period. Read the files.
In journal notes, `[x]` is done, `[-]` moved on, `[u]` is up (moving, not done) and `[d]` is
down (going badly). A weekly file's top sections are the goals for that week; its
"Reflections" and "How Well Did I Do?" review the week before. A past OKR file may hold the
user's own scores; use them. Commit totals run high (submodule bumps, rewritten or mirrored
repos), so treat them as rough.

If the period is longer than one month, run `gather.py` once for the whole period, then give
each month to a subagent: it runs `gather.py START END --no-toggl` for its month (the Toggl
free plan allows ~30 calls an hour), reads the files, and returns a short factual summary.
Work from those summaries.

## 2. Write the reflection

Write in chat, in plain words a friend would use.

- One line: the dates, the Toggl hours, the commits, the journal days.
- **What you did**: 4 to 7 themes, largest first. Join Toggl, git and the journal into one
  story for each theme, with hours and commits where they help. Say what got done, not what
  was worked on.
- **Against your vision**: use the vision and OKR files. Name what moved and what got no time
  at all.
- **Try next**: 3 changes, small enough to start next week. Quote the vision or OKR line that
  each one serves.

Be honest. If the data shows a weak period, say so. The journal is private: keep health and
personal matters short. If you see a secret (a key, a token, a SAS URL), never quote it; tell
the user the file so they can rotate it.
