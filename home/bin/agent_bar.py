#!/usr/bin/env python3
# The line the agent-bar mod pins under every Claude Code prompt:
#   $142 of $200 · waiting: api-2 · done: web-1, docs
# Spend is this month's Claude Code cost on this machine; ~/.config/agent-bar/cap holds the
# budget. "waiting" and "done" are tmux sessions you are not attached to: blocked on a
# question, or finished since you last had them open.
import glob
import json
import os
import subprocess
import sys
import time

DIR = os.path.expanduser("~/.cache/agent-bar")
LINE, SPEND, SESSIONS = (os.path.join(DIR, f) for f in ("line", "spend.json", "sessions.json"))
ME = os.path.abspath(__file__)
SPEND_TTL = 600
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


def refresh_spend():
    month = time.strftime("%Y-%m")
    # Same pinned ccusage as agent_usage.py, so both report the same dollars.
    out = subprocess.run(["npx", "-y", "ccusage@20.0.44", "claude", "monthly", "--since",
                          time.strftime("%Y%m01"), "--json"], capture_output=True, text=True, timeout=300).stdout
    cost = sum(r["totalCost"] for r in json.loads(out)["monthly"] if r["month"] == month)
    save(SPEND, json.dumps({"month": month, "cost": cost, "at": time.time()}))


def spend():
    month, now = time.strftime("%Y-%m"), time.time()
    s = load(SPEND)
    if s.get("month") != month:
        s = {"month": month, "cost": None, "at": 0}
    if now - s["at"] > SPEND_TTL:
        used = s["cost"] is None or any(os.path.getmtime(f) > s["at"]
                                        for f in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")))
        # Stamp first: other sessions then wait a full TTL, even if the refresh fails.
        save(SPEND, json.dumps({**s, "at": now}))
        if used:
            subprocess.Popen([sys.executable, ME, "--refresh-spend"], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return s["cost"]


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
    # Sessions run this from any project folder; npx must not see that folder's node_modules or .npmrc.
    os.chdir(DIR)
    if sys.argv[1:] == ["--refresh-spend"]:
        return refresh_spend()
    parts = []
    cost = spend()
    try:
        cap = float(open(os.path.expanduser("~/.config/agent-bar/cap")).read())
    except (OSError, ValueError):
        cap = None
    if cost is not None:
        parts.append(f"${cost:,.0f} of ${cap:,.0f}" if cap else f"${cost:,.0f} this month")
    waiting, done = sessions()
    if waiting:
        parts.append(names("waiting", waiting))
    if done:
        parts.append(names("done", done))
    line = " · ".join(parts)
    save(LINE, line)
    print(line)


main()
