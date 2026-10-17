---
name: research-resident
description: Hand a scoped research project to an autonomous resident that runs it end to end and leaves a paper draft to review. The user brings the scoping doc, either for a new project or for the next iteration of an existing draft, then a detached agent session executes it. Use when the user asks for a research resident, or wants to start or advance a research paper unattended.
---

# Research resident

The user scopes the work, the resident works it for a day and leaves a draft PR.

The user always brings a scoping doc. Never invent the research question, the baseline, or the stop criterion.

Two paths: **New**: the user hands over a scoping doc (and may name a backlog idea), then scaffold a repo. **Continue**: the user hands over an iteration scoping doc against an existing draft. Both end at §4.

The run gets no real-time feedback. Everything it needs is on disk before it starts. The scoping doc is the deliverable; the launch is plumbing.

## Settings

Read these from the "Research resident" section of `~/.claude/profile.md`. Ask the user for any that a step needs and the profile lacks.

- `GH_USER`: the GitHub account that owns new repos.
- `DEST`: the directory new repos go in.
- `BACKLOG` (optional): an `owner/repo` with idea notes under `ideas/`. Without it, skip §2.1.
- `TEMPLATE`: a cookiecutter template for new repos, as a local path or an `owner/repo`. Only §2.3 needs it.

## 1. New or continue

Before anything, you should know whether the user wants to start a new project or continue an existing one. If the user does not know, ask them to choose. If they do know, skip the question and go straight to the right section:

- **Start a new project** → §2.
- **Continue an existing project** → §3.

## 2. New project

### 2.1 The idea

Skip this step when there is no `BACKLOG` or the user names no idea.

The user names the idea. Match the name loosely (`crop noise` → `crop_label_noise_sim.md`) against `ideas/` and name the file you opened.

```sh
export GH_TOKEN="$(gh auth token --user "$GH_USER")"  # a private backlog needs the right account
gh api repos/$BACKLOG/contents/ideas --jq '.[].name'
gh api -H 'Accept: application/vnd.github.raw' repos/$BACKLOG/contents/ideas/<file>
```

The token must come from an account that can read the backlog. Read the file for background only; it does not travel into the new repo. The scoping doc is what the resident works from.

### 2.2 The scoping doc

The user provides it, as a file path or pasted in chat. It must cover these four blocks:

```markdown
# Answering Fundamental Questions about the paper
- What is the problem we want to solve?
- Why is it an interesting problem?
- What is the proposed solution?
- What are we expected to achieve from the solution?
- What potential impact the solution may have?

# Research Questions
- What are the research questions the paper should answer?
(By research questions, I mean precise, answerable queries that drive your investigation—not vague goals).

# Experimental Design
- What results should the paper produce (e.g., Figure, Table, etc.) to answer the questions?
- What are the baseline(s)? (If any).
- What results should we expect?

# Agent Goal
- What is the criteria used for the agent to stop (e.g., outperforming the baseline, spread between
  method results, tight confidence intervals, etc.; the user should be clear and specific here)?
```

When a block is missing or unfalsifiable, name exactly which one and ask about only that, in one exchange.

The Agent Goal is the block that sinks runs: `/goal` hands it to a checker that must tell yes from no.

| Sinks the run | Works |
|---|---|
| "the method works" | "val IoU beats the baseline by ≥3 points on 3 seeds" |
| "results look promising" | "the 95% CI of the difference excludes 0" |
| "the paper is done" | "paper compiles at ≤4 pages, every number traced to a results file" |

Every stop criterion needs its second half: **what done looks like when the idea is wrong.** Without it the resident grinds against a false hypothesis. Ask for something like "…or 8 configurations have been tried and none beats the baseline, in which case write the negative result up as the paper."

Hold the doc until §2.3 scaffolds the repo; it lands as `RESEARCH_BRIEF.md` at the repo root.

### 2.3 Scaffold the repo

`TEMPLATE` is a cookiecutter, not a GitHub template repo. When it is an `owner/repo`, clone it (or reuse a local clone) and run cookiecutter over the clone.

The commands below assume a template with `research-writing` and `claude-code` packs, a `make verify` target and a LaTeX paper at `paper/paper.tex`. With another template, swap in its options and checks; the resident needs `paper/paper.tex` and one verify command.

```sh
uvx cookiecutter --no-input -o "$DEST" "<local clone of TEMPLATE>" \
  project_name="<Project Name>" \
  project_short_description="<one line>" \
  github_username=$GH_USER \
  research-writing=yes \
  claude-code=yes
```

`research-writing=yes` keeps `paper/`, `claude-code=yes` keeps `.claude/`. The post-gen hook deletes both when their pack is off, and neither is pleasant to add back. Add any other pack the idea needs now: `deep-learning`, `geo-skills`, `azure-ml`, `viz`. `agent-workflows` is already on. `project_slug` derives from `project_name`: Title Case in, `snake_case` out.

The post-gen hook runs `uv lock`, which needs PyPI. **If it fails, cookiecutter deletes the whole generated tree**, so a failed run is safe to retry once the network is back. `Socket is not connected` against `files.pythonhosted.org` while `pypi.org` answers means the CDN is blocked, not the template.

The paper ships prebuilt LaTeX artifacts (`paper.aux`, `paper.bbl`, …) that misdirect `latexmk` into running `bibtex` on a stub aux file, failing with "I found no \citation commands". Delete them before the first commit.

```sh
set -e                                        # a red gate must not reach gh repo create
cd "$DEST/<project_slug>"
rm -f paper/paper.{aux,bbl,blg,fdb_latexmk,fls,log,out,pdf,synctex.gz}
uv sync --frozen
make verify                                   # ~20s on a fresh scaffold. Must pass.
(cd paper && latexmk -pdf -interaction=nonstopmode paper.tex)   # must exit 0
git add -A && git commit -qm "Scaffold from template"

export GH_TOKEN="$(gh auth token --user "$GH_USER")" # git spawns the helper, so export it
git config --local credential.helper '!gh auth git-credential'
gh repo create "$GH_USER/<project_slug>" --private --source=. --remote=origin --push
```

Every worktree cut from this repo inherits the repo-local credential helper, which is what lets the unattended push work.

Now write the scoping doc to `RESEARCH_BRIEF.md` at the repo root, commit it, then go to §4:

```sh
git add RESEARCH_BRIEF.md && git commit -qm "Add research brief" && git push -u origin main
```

## 3. Continue an existing project

### 3.1 The repo

The user should already be in the project directory, no need to clone or cd into it. Confirm `paper/paper.tex` exists before going further; a repo with no paper is the wrong target.

### 3.2 The iteration scoping doc

The user provides a scoping doc for the next iteration, in the same format as §2.2. It replaces `RESEARCH_BRIEF.md` at the repo root, written into the worktree made in §4; git history keeps the previous round's.

The Agent Goal is not optional and does not carry over from last time. A revision round without a fresh stop criterion polishes the paper forever.

## 4. Launch the resident

Worktree first, docs second. They must exist inside the checkout the session runs in, and `artifacts/` may be gitignored, so nothing travels there by itself.

```sh
REPO="<repo path>"                            # scaffolded repo (§2) or existing one (§3)
SLUG="resident-$(date +%F)-<project>"         # lowercase, [a-z0-9-] only
WT="$HOME/.claude/resident-worktrees/$SLUG"

BASE="$(git -C "$REPO" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
[ -n "$BASE" ] || BASE="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"

git -C "$REPO" fetch origin --quiet
git -C "$REPO" worktree add -b "$SLUG" "$WT" "origin/$BASE"
mkdir -p "$WT/artifacts"
```

Branch from `origin/<base>`, never from a possibly dirty HEAD. The same `SLUG` is the branch, the worktree directory, and the tmux session name.

The brief is the run's entire memory. Write it to `$WT/artifacts/$SLUG.md`:

```markdown
# Research resident: <project>, <date>

## Assignment
Work `RESEARCH_BRIEF.md` from Research Questions through to a paper draft.

## Stop criterion
<verbatim from the user, including the what-if-it-is-wrong half>

## Verification
- `make verify` exits clean.
- `cd paper && latexmk -pdf -interaction=nonstopmode paper.tex` exits 0.
- Every number in `paper.tex` traces to a file under `artifacts/` written by a committed script.

## Guardrails
- Compute: <local only | may submit cloud jobs | may submit and iterate>
- Baseline before method. A comparison with no baseline cannot satisfy the stop criterion.
- ≥3 seeds behind any comparison claim; report the spread, not just the mean.
- Never invent a number. If it is not in a results file, it does not go in the paper.
- GitHub: <owner>/<name>, account <account>, PR base <branch>.
- Never: commit to main, force push, delete or overwrite shared cloud data, cancel someone
  else's job.

## Context
<3-6 bullets: key scripts, where data lives, what the last round left open>

## Experiment ledger
| # | when | config | metric | seeds | result | in paper? |
|---|------|--------|--------|-------|--------|-----------|
```

With several GitHub accounts, check `git -C <repo> config --local credential.helper` first. When it is not `!gh auth git-credential`, say so in Guardrails: the system credential helper may hand back the wrong account and the push fails with a misleading "Repository not found".

Launch detached:

```sh
KEEPAWAKE=""; command -v caffeinate >/dev/null && KEEPAWAKE="caffeinate -is "
command tmux new-session -d -s "$SLUG" -c "$WT" \
  "${KEEPAWAKE}claude --enable-auto-mode '/goal <condition>'"
```

Use `command tmux`, never bare `tmux`: the oh-my-zsh plugin shadows it with a function that does not load non-interactively. On the Mac, `caffeinate -is` blocks idle and system sleep for the session's lifetime; without it the Mac sleeps mid-afternoon and the run stalls silently. The lid has to stay open. Linux has no `caffeinate`, so the prefix is empty there.

The condition caps at **4000 characters**, so point it at the brief rather than restating it:

> Work the brief at `artifacts/<slug>.md` until its Stop criterion holds. Read the brief and its
> Experiment ledger first; never rerun a configuration already recorded there. Run the baseline
> before the method. Do one experiment at a time, append a ledger row (config / metric / seeds /
> result), and put every number you report into a file under `artifacts/` written by a committed
> script. Keep `paper/paper.tex` current as results land, following `paper/README.md`. Commit each
> kept unit to the current branch; never commit to main; never force push. After the first commit,
> push and open a **draft** PR with `gh pr create --draft`, and keep its Status section current.
> Never ask questions, self-verify, report honestly what you skipped. You are DONE when the Stop
> criterion holds, `make verify` exits clean, and
> `cd paper && latexmk -pdf -interaction=nonstopmode paper.tex` exits 0, **or** when the same
> blocker has defeated three consecutive attempts, in which case write a final ledger entry naming
> the blocker, push, put it in the PR body, and stop.

The three-strikes clause is the escape valve: `/goal` installs a `Stop` hook that refuses to let the session end until its condition is met, so an unsatisfiable condition grinds until the session dies.

## 5. Confirm the launch took

Never report success without reading the pane. Run this as a **background** Bash call; the tool blocks a foreground `sleep`.

```sh
sleep 20; command tmux capture-pane -p -t "$SLUG" | tail -30
```

- **Trust dialog** (`Is this a project you created or one you trust?`): a fresh worktree is a new path, so it appears every time and the session sits there forever. Option 1 is preselected, so `command tmux send-keys -t "$SLUG" Enter` clears it. Then capture again.
- **`Goal set: <condition>`** plus `◎ /goal active` in the status line is the confirmation that matters. When the condition shows up as an ordinary user message instead, the goal never registered: kill the session, fix the launch, retry. Never leave a resident running without a goal.

## Report shape

End with: the tmux session name and `command tmux attach -t <slug>`; the brief path; the stop criterion in one sentence; and when to look. A resident gets checked at the end of the day, not watched. Once the PR is merged or closed, run `git -C <repo> worktree remove ~/.claude/resident-worktrees/<slug>`.
