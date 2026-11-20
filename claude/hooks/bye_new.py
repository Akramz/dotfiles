#!/usr/bin/env python3
# Stop hook of the bye skill: types `/new x` into this tmux pane once the turn is idle,
# without pressing Enter, so the user can read the goodbye and decide.
import os
import shutil
import subprocess

pane = os.environ.get("TMUX_PANE")
tmux = shutil.which("tmux")
if pane and tmux:
    subprocess.Popen(
        ["sh", "-c", 'sleep 1.5; "$0" send-keys -t "$1" -l "/new x"',
         tmux, pane],
        start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
