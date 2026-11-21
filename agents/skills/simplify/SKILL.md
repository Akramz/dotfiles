---
name: simplify
description: Clean up the changed code without changing behavior. Reviews the diff for reuse, simplification, efficiency and altitude issues with 4 parallel subagents, then applies the fixes. Quality only, not bugs (use /code-review for that). Use when the user runs /simplify.
argument-hint: "[target]"
---

# /simplify → 4 cleanup agents in parallel → apply the fixes

You are improving the quality of the changed code, not hunting for bugs. Review it for reuse,
simplification, efficiency and altitude issues, then fix what you find. Do not look for
correctness bugs: that is what `/code-review` is for.

**Hard rule:** you **must** run the four angles as four subagents. pi has the `subagent` tool, so
in pi the fan-out is never optional, however small the diff.
Only if no subagent tool exists at all, do all four angles yourself, one after the other.

## Phase 0: Gather the diff

If the user named a target (a path, branch, commit range or PR number), review that: `gh pr diff <n>`
for a PR, `git diff main...<branch>` for a branch. Otherwise run `git diff HEAD` and also read any
untracked files from `git status --short`. If there is no change, say so and stop.

## Phase 1: Review (4 cleanup agents in parallel)

Launch **4 independent review subagents in one message** so they run at the same time:

- **pi:** the `subagent` tool in parallel mode, `tasks: [{ agent: "reviewer", task }, ...]`.

Give each agent the diff (or the exact command to get it), the repo path, and **one** of the four
angles below. Each returns its findings as `file:line`, a one-line summary, and the concrete cost:
what is duplicated, wasted or harder to maintain. Agents only read; they never edit.

### Reuse
Flag new code that re-implements something the codebase already has. Grep shared/utility modules
and files next to the change, and name the existing helper to call instead.

### Simplification
Flag unnecessary complexity the diff adds: redundant or derivable state, copy-paste with slight
variation, deep nesting, dead code left behind. Name the simpler form that does the same job.

### Efficiency
Flag wasted work the diff introduces: redundant computation or repeated I/O, independent operations
run one after another, blocking work added to startup or hot paths. Also flag long-lived objects
built from closures that keep a large enclosing scope alive. Name the cheaper alternative.

### Altitude
Check that each change fixes the root cause at the right depth rather than patching a symptom.
Special cases layered on shared infrastructure are a sign the fix is not deep enough: prefer the
simpler, more general change to the underlying mechanism, and name that change.

## Phase 2: Apply the fixes

Wait for all four agents. Dedup findings that point at the same line or mechanism, then fix each
remaining one directly in the working tree. Skip any finding whose fix would change intended
behavior, need changes well outside the reviewed diff, or that you judge a false positive. Note the
skip instead of arguing with it. Run the repo's fast checks (lint, quick tests) if it has them.

Finish with a short summary: what you fixed (`file:line`, one line each), what you skipped and why,
or that the code was already clean. **Say which mode ran**: "4 parallel subagents" or "single pass,
no subagent tool", so the reader is not misled.
