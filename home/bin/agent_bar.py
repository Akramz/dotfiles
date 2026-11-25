#!/usr/bin/env python3
# The line the agent-bar mod pins under every Claude Code and pi prompt:
#   waiting: api-2 · done: web-1, docs
# "waiting" and "done" are tmux sessions you are not attached to: blocked on a question,
# or finished since you last had them open.
import json
import os
import sys

DIR = os.path.expanduser("~/.cache/agent-bar")
LINE = os.path.join(DIR, "line")
SESSIONS = os.path.join(DIR, "sessions.json")
SHOWN = 3


def load(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return {}


def save(path, text):
    tmp = f"{path}.{os.getpid()}"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def sessions():
    sys.path.insert(0, os.path.expanduser("~/.config/tp"))
    import tp_tui as tp  # its classify() is what tp's state tags use
    rc, out = tp.tmux("list-sessions", "-F", "#{session_name}\t#{session_attached}")
    rows = [r.split("\t") for r in out.splitlines()] if rc == 0 else []
    # Every pane in one tmux call: with dozens of sessions, one call each takes a second.
    sep, args = "\x1f", []
    for name, _ in rows:
        args += ["capture-pane", "-p", "-t", f"={name}:", ";", "display-message", "-p", sep, ";"]
    panes = tp.tmux(*args[:-1])[1].split(sep + "\n") if rows else []
    # Per session: running, unseen (stopped running while you were away), or seen.
    prev, cur, waiting, done = load(SESSIONS), {}, [], []
    for (name, attached), pane in zip(rows, panes):
        state, away = tp.classify(pane), attached == "0"
        unseen = away and state != "running" and prev.get(name) in ("running", "unseen")
        cur[name] = "running" if state == "running" else "unseen" if unseen else "seen"
        if away and state == "waiting":
            waiting.append(name)
        elif unseen:
            done.append(name)
    save(SESSIONS, json.dumps(cur))
    return waiting, done


def names(label, items):
    more = f" +{len(items) - SHOWN}" if len(items) > SHOWN else ""
    return f"{label}: {', '.join(items[:SHOWN])}{more}"


def main():
    os.makedirs(DIR, exist_ok=True)
    parts = []
    waiting, done = sessions()
    if waiting:
        parts.append(names("waiting", waiting))
    if done:
        parts.append(names("done", done))
    line = " · ".join(parts)
    save(LINE, line)
    print(line)


main()
