---
name: push
description: Git add, commit, and push your contributions, to `main` or as a PR. Use when the user runs /push.
---

# Push

Git add, commit, and push your contributions.

Before you commit, run the repo's fast checks: `make verify` if it exists, otherwise its test command. If they still fail after three fix attempts, stop and report the failure. Do not commit or push. If the repo has no checks, say so in one line.

Open a PR if you think the change needs human review, for example if it changes the system design or introduces a new concept. Give a one-line reason and point to what to review. Otherwise push straight to `main`.
