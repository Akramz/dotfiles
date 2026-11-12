---
name: copilot
description: Hand a coding job to GitHub Copilot CLI so it runs on Copilot's budget instead of Claude's. Use only when the user runs /copilot or explicitly asks to give a job to Copilot. For Claude Code only; Copilot itself must not use this skill.
---

# Copilot

Copilot does the work; you brief it and check the result, cheaply.

## Brief

Copilot sees nothing of this chat. Write a brief that stands alone: the goal, the files
that matter, what done looks like and how to check it. Ask Copilot to run that check itself
and to end with a short summary: the check's result, the files it changed, and anything it
skipped.

Pick an unused kebab-case name for the job; the session is `delegated-<name>`. Write the
brief to `<scratchpad>/delegated-<name>.md`.

## Launch

```sh
N=delegated-<name>; DIR=<repo>; S=<scratchpad>
ID=$(uuidgen | tr A-Z a-z); LOG=$S/$N.log
KEEPAWAKE=""; command -v caffeinate >/dev/null && KEEPAWAKE="caffeinate -is "
command tmux new-session -d -s "$N" -c "$DIR" "set -o pipefail; ${KEEPAWAKE}copilot \
  -p \"\$(cat $S/$N.md)\" --session-id $ID --name $N --model claude-opus-5.5 \
  --reasoning-effort high --allow-all 2>&1 | tee $LOG; echo \$? > $LOG.done; \
  exec copilot --resume=$ID"
```

The session runs the job live, then turns into an interactive Copilot chat on the same
conversation, so the user can attach any time and keep going. `--allow-all` is needed:
`-p` cannot ask, and without it Copilot refuses paths outside `DIR`. Use a different
model only when the user asks.

Tell the user the session name and that `tattach delegated-<name>` or `tp` opens it.

## Wait

Wait with a **background** Bash call, so you get a notice when the job ends:

```sh
until [ -f "$LOG.done" ]; do sleep 15; done; echo "exit $(cat "$LOG.done")"; tail -c 3000 "$LOG"
```

Don't poll the pane. If the user asks how it is going, `tail -c 1500 "$LOG"`.

## Report

Start from Copilot's summary and `git diff --stat` in `DIR`. Read only the hunks you need
to judge the work (`git diff -- <path>`), never lockfiles or generated files. If you rerun
the check, keep its output short (`-q`, `| tail -n 20`). Report what Copilot did, whether
it holds up, and anything it skipped. Don't fix its mistakes yourself: say what is wrong,
and offer a follow-up job.

Leave the tmux session running; it is the user's chat now.

## Gotchas

- Use `command tmux`: the oh-my-zsh plugin shadows `tmux` in non-interactive shells.
- Two jobs at once must work in different folders or worktrees.
- In a folder Copilot does not trust yet, the chat opens on a trust prompt after the job.
  The job itself is not affected.
