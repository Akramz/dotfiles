---
name: push
description: Git add, commit, and push your contributions, straight to main or as a PR when the change needs human review. Use when the user runs /push.
---

# Push

Git add, commit, and push your contributions.

First decide whether the change is critical: it changes the system design, edits building blocks or primitives, or adds a new component.

- **Not critical:** push straight to `main`. No human review needed.
- **Critical:** push to a new branch and open a PR with `gh pr create`. Give the user the PR number and URL, and say in one line why it needs review.
