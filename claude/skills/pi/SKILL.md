---
name: pi
description: Hand a coding job to a pi session so it runs on the Copilot seat instead of Claude's budget. Use only when the user runs /pi or explicitly asks to give a job to pi. For Claude Code only; pi itself must not use this skill.
---

# pi

pi does the work; you brief it and check the result, cheaply.

## Brief

pi sees nothing of this chat. Write a brief that stands alone: the goal, the files
that matter, what done looks like and how to check it. Ask pi to run that check itself
and to end with a short summary: the check's result, the files it changed, and anything it
skipped.

Pick an unused kebab-case name for the job; the session is `delegated-<name>`. Write the
brief to `<scratchpad>/delegated-<name>.md`.

## Launch

```sh
N=delegated-<name>; DIR=<repo>; S=<scratchpad>
ID=$(uuidgen | tr A-Z a-z); LOG=$S/$N.log
KEEPAWAKE=""; command -v caffeinate >/dev/null && KEEPAWAKE="caffeinate -is "
command tmux new-session -d -s "$N" -c "$DIR" "set -o pipefail; ${KEEPAWAKE}pi \
  -p \"\$(cat $S/$N.md)\" --session-id $ID --name $N \
  2>&1 | tee $LOG; echo \$? > $LOG.done; \
  exec pi --session $ID"
```

pi runs the job in print mode, then the session turns into an interactive pi chat on the
same conversation, so the user can keep going. Print mode shows only pi's final answer, so
the pane stays blank until the job ends. `pi/settings.json` already picks Opus 5.5 at high
effort; add `--model` only when the user asks for another model.

Tell the user the session name, that `tattach delegated-<name>` or `tp` opens it, and that
the pane fills in when the job ends.

### On an ssh host

When the user names a host (`host:dir`), run the job there so the Mac can sleep. The host
needs pi logged in (`/login github-copilot` there once) and DIR checked out. Changes stay on
the host, so if the user wants them back, brief pi to commit to a branch and push.

`~/bin/rsh <host> '<cmd>'` runs a command there; stdin passes through. Save the Launch
block to `<scratchpad>/$N.sh` with `DIR=<dir on the host>` and `S=~/.agent-jobs`, then:

```sh
~/bin/rsh <host> "mkdir -p ~/.agent-jobs && cat > ~/.agent-jobs/$N.md" < <scratchpad>/$N.md
~/bin/rsh <host> "bash -s" < <scratchpad>/$N.sh
```

Wait on the host in one background call; the outer loop only retries when ssh drops:

```sh
until ~/bin/rsh <host> "until [ -f ~/.agent-jobs/$N.log.done ]; do sleep 15; done; echo exit \$(cat ~/.agent-jobs/$N.log.done); tail -c 3000 ~/.agent-jobs/$N.log"; do sleep 60; done
```

Run Report's git commands through rsh. The user opens the session with `pie <N> <host>:<dir>`.

## Wait

Wait with a **background** Bash call, so you get a notice when the job ends:

```sh
until [ -f "$LOG.done" ]; do sleep 15; done; echo "exit $(cat "$LOG.done")"; tail -c 3000 "$LOG"
```

Don't poll the pane. If the user asks how it is going, say it is still running; the log is
empty until the job ends.

## Report

Start from pi's summary and `git diff --stat` in `DIR`. Read only the hunks you need
to judge the work (`git diff -- <path>`), never lockfiles or generated files. If you rerun
the check, keep its output short (`-q`, `| tail -n 20`). Report what pi did, whether
it holds up, and anything it skipped. Don't fix its mistakes yourself: say what is wrong,
and offer a follow-up job.

Leave the tmux session running; it is the user's chat now.

## Gotchas

- Use `command tmux`: the oh-my-zsh plugin shadows `tmux` in non-interactive shells.
- Two jobs at once must work in different folders or worktrees.
- pi has no permission prompts: every tool call runs. Brief it on what it must not touch.
