@~/.claude/profile.md

# Agent Rules

## Writing

- Write plain, simple, easy-to-understand, natural American English. Active voice.
- Don't use a foreign phrase, a scientific word, or jargon when an everyday American English word works.
- No fluff, no filler, no padding, no redundant summaries, no boilerplate. 
- If a one-liner answer works, give a one-liner. Keep caveats and disclaimers short.
- Explain at a high level unless I ask for depth.
- Match document length to the task.

## Coding

- Implement the simplest working solution first. Add complexity only when it's needed.
- No comments. No docstrings.
- Focus on the cases people are likely to run into, not every possible one (e.g., if something only breaks when it's misused, it usually isn't worth fixing).

## Reporting

- Before the first tool call, say in one sentence what you're about to do.
- While working, update me only when you find something important or change direction.
- When you finish, lead with the outcome: the first sentence answers "what happened" or "what did you find". Detail after that.
- Do not stop early and claim completion. Do not silently relax constraints.
- Before you call a code change done, run the repo's `verify` skill if it has one.
- If a check still fails after three fix attempts, stop. Tell me what fails, what you tried, and your best guess at the cause.
- Investigate every test failure, including timeouts.
- When it fits, show a screenshot or video that proves your work is correct, so I can check it quickly.
- If you think I'm wrong, say so and argue it.

## Tests

- Each test should check real usage on real inputs. Do not write trivial, redundant, or mock-only tests, and delete them when you find them.
- Write end-to-end tests on small real inputs. Add differential tests (old and new code on the same inputs) for rewrites, and property tests (Hypothesis) where a clear invariant exists. Do not write unit tests.
- Never fix a flaky test with sleeps, retries, or skips. Find the cause, or delete the test and say why.
- The full test suite must run in under 30 seconds. If it's slower, cut or speed up tests until it is.

## Git

- Work on `main`. Do not create a branch, worktree, or PR unless I ask or `/push` calls for one.
- Commit and push only when I ask (for example with /push). Never commit or push as the tail
  of another task. The same goes for submodules.

## Follow-ups

- Open follow-ups live in `~/projects/Personal/dotfiles/claude-memory/Followups.md`, one per line: `- YYYY-MM-DD what to do (memory: slug)`.
- Add one when I ask, or when something is waiting on a person or a date.
- When you finish one, delete its line.

## This machine

- Python: `uv` for per-project envs and scripts.

Per-OS notes, work-machine notes (only after `install.sh --with-work`), then untracked notes
about this particular machine (absent on most):

@~/.claude/os.md
@~/.claude/work.md
@~/.claude/local.md
