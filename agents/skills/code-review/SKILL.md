---
name: code-review
description: Review the current diff, or a PR number, branch or path, for correctness bugs at an effort level (low, medium, high, max), using parallel finder subagents and one verifier per finding. Pass --fix to apply the fixes after the review. Use when the user runs /code-review or /review.
argument-hint: "[low|medium|high|max] [target] [--fix]"
---

# /code-review → finder angles in parallel → verify each candidate → ranked findings

**Hard rule:** at medium, high and max you **must** run the finders and verifiers as subagents. pi
has the `subagent` tool, so in pi the fan-out is never optional, however small the diff. A single pass, where you do each angle and verification yourself,
is allowed only at `low` or when no subagent tool exists at all.

Parse the arguments: an effort level (`low`, `medium`, `high`, `max`; default **medium**), an
optional target, and `--fix`.

## Phase 0: Gather the diff

- A PR number or URL: `gh pr diff <n>` (and `gh pr view <n>` for its base).
- A branch: `git diff main...<branch>` (use the real default branch).
- A path: the diff of that path only.
- Nothing: `git diff origin/HEAD...HEAD` plus `git diff HEAD` (committed and uncommitted work).
  If both are empty, fall back to `git diff HEAD~1`.

If there is no change, say so and stop.

## Subagents

Run finders and verifiers as **independent subagents, all of a phase in one message**:

- **pi:** the `subagent` tool in parallel mode, `tasks: [{ agent: "reviewer", task }, ...]`
  (at most 8 tasks per call; make several calls in the same message for more).

Give each subagent the diff (or the exact command to get it), the repo path, and its one angle or
candidate. Subagents only read; they never edit.

## Effort levels

| Level | Phase 1 finders | Candidates each | Phase 2 verify | Phase 3 sweep | Report at most |
|---|---|---|---|---|---|
| low | none: one pass over the diff yourself | — | none | no | 4 |
| medium | 8 angles: A, B, C + Reuse, Simplification, Efficiency, Altitude, Conventions | 6 | 1 vote, precision | no | 8 |
| high | the same 8 angles | 6 | 1 vote, recall-biased | no | 10 |
| max | 10 angles: A–E + Reuse, Simplification, Efficiency, Altitude, Conventions | 8 | 1 vote, recall-biased | yes | 15 |

**low:** read the unified diff once, skip test and fixture hunks, and flag only runtime-correctness
bugs visible from the hunk alone (inverted condition, off-by-one, null deref where the value can be
absent, removed guard, falsy-zero check, missing `await`, wrong-variable copy-paste, swallowed
error), plus new code that duplicates a helper visible in the diff and dead code left behind.

## Phase 1: Find candidates

Each finder surfaces candidates with `file`, `line`, a one-line `summary` and a concrete
`failure_scenario` (inputs or state → wrong output or crash). Pass every candidate with a nameable
failure scenario through; do not silently drop half-believed ones. Do not let one angle suppress
another.

### Angle A: line-by-line diff scan
Read every hunk line by line, then the enclosing function. Bugs in unchanged lines of a touched
function are in scope. For every line ask: what input, state, timing or platform makes this line
wrong? Inverted conditions, off-by-one, null/undefined deref, missing `await`, falsy-zero checks,
wrong-variable copy-paste, error swallowed in catch, unescaped regex metacharacters.

### Angle B: removed-behavior auditor
For every line the diff deletes or replaces, name the invariant it enforced, then find where the new
code re-establishes it. If you cannot, that is a candidate: a removed guard, a dropped error path, a
narrowed validation, a deleted test that covered a real case.

### Angle C: cross-file tracer
For each changed function, grep its callers and check whether the change breaks a call site: a new
precondition, a changed return shape, a new exception, an ordering dependency. Check callees too.

### Angle D: language-pitfall specialist (max only)
The classic pitfalls of the diff's language: JS falsy-zero, `==` coercion, loop-variable capture;
Python mutable default args, late-binding closures; Go nil-map write; SQL injection; timezone/DST
drift; float equality. Flag any instance the diff introduces.

### Angle E: wrapper/proxy correctness (max only)
When the change adds or modifies a type that wraps another (cache, proxy, decorator, adapter), check
that every method routes to the wrapped instance and not back through a registry or global, and that
the wrapper forwards every method callers use.

### Reuse
Flag new code that re-implements something the codebase already has; name the helper to call.

### Simplification
Flag unnecessary complexity: derivable state, copy-paste with slight variation, deep nesting, dead
code. Name the simpler form.

### Efficiency
Flag wasted work: repeated computation or I/O, independent operations run in sequence, blocking work
on startup or hot paths. Name the cheaper alternative.

### Altitude
Flag fixes that patch a symptom instead of the root cause, such as special cases layered on shared
infrastructure. Name the deeper, more general change.

### Conventions
Find the instruction files that govern the changed code: the repo-root `CLAUDE.md` and `AGENTS.md`,
plus any `CLAUDE.md`, `CLAUDE.local.md` or `AGENTS.md` in an ancestor directory of a changed file.
Also read the repo-root `REVIEW.md`: it lists what this repo's owner wants flagged.
Your user-level rules are already in your context; do not search for them. Flag a violation only when
you can quote the exact rule and the exact line that breaks it. If no file applies, return nothing.

Cleanup, altitude and conventions candidates use the same shape; in `failure_scenario`, state the
concrete cost (what is duplicated, wasted, harder to maintain, or which rule is broken). Correctness
bugs always outrank them when the cap forces a cut.

## Phase 2: Verify (not at low)

Dedup candidates that point at the same line and mechanism; keep the one with the most concrete
failure scenario. Run **one verifier subagent per remaining candidate**, all in parallel. Give it the
diff, the relevant files and the candidate. It returns exactly one of:

- **CONFIRMED**: it can name the inputs or state that trigger the bug and the wrong result.
- **PLAUSIBLE**: the mechanism is real, the trigger is uncertain (timing, environment, rare path).
- **REFUTED**: factually wrong (quote the line that proves it), provably impossible, already
  handled (cite the guard), or pure style with no observable effect.

At medium, keep CONFIRMED only, plus PLAUSIBLE when the trigger is realistic. At high and max, keep
CONFIRMED and PLAUSIBLE; do not refute a candidate just for depending on realistic runtime state
(races, cold caches, missing optional fields, retries, partial failures).

## Phase 3: Sweep for gaps (max only)

Run one more finder as a fresh reviewer who has the verified list. It re-reads the diff and enclosing
functions looking **only** for defects not already listed, especially: moved code that dropped a
guard, second-tier footguns (defaults evaluated once, lock-scope shrink, predicates with side
effects), setup/teardown asymmetry in tests, flipped config defaults. Up to 8 new candidates; verify
them like Phase 2. An empty sweep is fine; do not pad.

## Output

Give each finding a severity:

- 🔴 **important**: a bug this change adds or makes worse, even if the trigger is rare.
- 🟣 **pre_existing**: a bug that was already there and that this change only fails to fix.
- 🟡 **nit**: worth fixing but harms nobody (a broken rule, a misleading log line).

List at most the level's cap, most severe first (important, then pre_existing, then nit):

```
1. 🔴 path/to/file.ext:123 — The problem as a user of the code sees it. Where it happens and what
   sets it off. Fix: the change to make. [CONFIRMED]
   Failure: concrete inputs/state → wrong output/crash
```

Report a mistake repeated in several places once and name the other places. If nothing survives,
say "No findings." End with one line saying which mode ran: the level, how many finder and
verifier subagents ran, or "single pass, no subagent tool".

With `--fix`, apply the fixes for the reported findings after the report, run the repo's fast checks,
and list what you changed. Without `--fix`, do not edit anything.
