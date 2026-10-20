@~/.claude/profile.md

# Agent Rules

## Writing

- Write plain, simple English. Active voice.
- No fluff, no filler, no padding, no redundant summaries, no boilerplate. 
- If a one-liner answer works, give a one-liner. Keep caveats and disclaimers short.
- Explain at a high level unless I ask for depth.
- Match document length to the task.

## Coding

- Implement the simplest working solution first. Add complexity only when it's needed.
- Minimal comments. No docstrings.
- Before writing a plan with `/html-plan`, check that I gave you a way to verify the work (a test, a command, a page to check). If I didn't, push back and ask for one first.

## Reporting

- Before the first tool call, say in one sentence what you're about to do.
- While working, update me only when you find something important or change direction.
- When you finish, lead with the outcome: the first sentence answers "what happened" or "what did you find". Detail after that.
- Do not stop early and claim completion. Do not silently relax constraints.
- Investigate every test failure, including timeouts.
- If you think I'm wrong, say so and argue it.

## Tests

- Only write tests for things that really matter. Skip trivial or redundant ones.
- The full test suite must run in under 30 seconds. If it's slower, cut or speed up tests until it is.

## Git

- Work on `main`. Do not create a branch, worktree, or PR unless I ask or `/push` calls for one.
- Commit and push only when I ask (for example with /push). Never commit or push as the tail
  of another task. The same goes for submodules.

## This machine

- Python: Miniforge at `~/miniforge3`; per-project envs via `mamba env create` or `uv`.

Per-OS notes, work-machine notes (only after `install.sh --with-work`), then untracked notes
about this particular machine (absent on most):

@~/.claude/os.md
@~/.claude/work.md
@~/.claude/local.md
