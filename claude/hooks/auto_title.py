#!/usr/bin/env python3
# Puts a name on the prompt bar so you don't have to /rename. Claude Code already writes an
# ai-title after the first prompt but shows it only in /resume; on a later prompt this hook
# hands it back as a short hyphenated sessionTitle. A /rename (custom-title) wins.
import json
import re
import sys

STOP = {"a", "an", "and", "the", "of", "for", "to", "in", "on", "with", "from", "by"}

ai = None
try:
    with open(json.load(sys.stdin)["transcript_path"]) as f:
        for line in f:
            if '"type":"custom-title"' in line:
                sys.exit(0)
            if '"type":"ai-title"' in line:
                ai = json.loads(line).get("aiTitle")
except (KeyError, OSError, ValueError):
    sys.exit(0)

words = [w for w in re.findall(r"[a-z0-9]+", (ai or "").lower()) if w not in STOP]
if words:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit", "sessionTitle": "-".join(words[:4])}}))
