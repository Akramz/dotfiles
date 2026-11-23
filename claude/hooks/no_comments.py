#!/usr/bin/env python3
import json
import os
import re
import sys
from collections import Counter

MARK = {e: m for m, exts in [
    (("#",), ".py .sh .bash .zsh .rb .pl .r .jl"),
    (("//", "/*"), ".js .mjs .cjs .ts .tsx .jsx .go .rs .c .h .cc .cpp .hpp .java .kt .swift .cs .scala .dart"),
    (("--",), ".lua .sql .hs"),
] for e in exts.split()}
PRAGMA = re.compile(r"#!|noqa|type:|ty:|nosec|pylint|pyright|mypy|ruff|isort|fmt:|pragma|shellcheck"
                    r"|eslint|@ts-|prettier|biome-|nolint|go:|luacheck|-\*-")
UV_META = re.compile(r"(?ms)^# /// script$.*?^# ///$")

def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""

def comments(text, starts):
    lines = map(str.strip, UV_META.sub("", text).splitlines())
    return Counter(s for s in lines if s.startswith(starts) and not PRAGMA.search(s))

data = json.load(sys.stdin)
inp = data["tool_input"]
path = inp["file_path"]
write = data["tool_name"] == "Write"
new = inp["content"] if write else inp["new_string"]

ext = os.path.splitext(path)[1].lower()
starts = MARK.get(ext)
if not starts and not ext and (new if write else read(path)).startswith("#!"):
    starts = ("#",)
if not starts:
    sys.exit(0)

old = read(path) if write else inp["old_string"]
added = list((comments(new, starts) - comments(old, starts)).elements())
if added:
    sys.stderr.write("No code comments (CLAUDE.md). Redo the change without these lines:\n"
                     + "\n".join(added[:5]))
    sys.exit(2)
