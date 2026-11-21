#!/usr/bin/env python3
# Adds a "Goal Verification" section to every /html-plan plan, without forking the plugin.
# UserPromptExpansion / PostToolUse(Skill): inject the rule. PostToolUse(Bash pack.mjs): reject plans without it.
# The rule lives in html_plan_rule.md.
import json
import os
import re
import shlex
import sys

def rule():
    return open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "html_plan_rule.md")).read().strip()


def find_plan(cmd, cwd):
    try:
        toks = shlex.split(cmd)
    except ValueError:
        toks = cmd.split()
    base = cwd
    for i, t in enumerate(toks):
        if t == "cd" and i + 1 < len(toks):
            base = os.path.join(base, os.path.expanduser(toks[i + 1]))
    for i, t in enumerate(toks):
        if t.endswith("pack.mjs"):
            for a in toks[i + 1:]:
                if a.endswith(".html") and not a.endswith((".packed.html", ".artifact.html")):
                    return os.path.normpath(os.path.join(base, os.path.expanduser(a)))
    return None


def problems(html):
    m = re.search(r"<doc-claim\b[^>]*\baux=[\"']verify[\"'][^>]*>", html)
    if not m:
        return ['no <doc-claim aux="verify">']
    sec = html[m.end():]
    sec = sec[:sec.find("</doc-claim>")] if "</doc-claim>" in sec else sec
    out = []
    if "Goal Verification" not in sec.split("<doc-draft")[0]:
        out.append('its first <p> must start with "<b>Goal Verification</b>"')
    d = re.search(r"<doc-draft\b[^>]*>\s*<script type=[\"']?text/plain[\"']?>(.*?)</script>", sec, re.S)
    if not d or not d.group(1).strip():
        out.append("no non-empty <doc-draft> with the checks")
    return out


def main():
    ev = json.load(sys.stdin)
    name = ev.get("hook_event_name")
    if name == "UserPromptExpansion":
        if "html-plan" in ev.get("command_name", ""):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": name, "additionalContext": rule()}}))
        return
    if name != "PostToolUse":
        return
    tool, inp = ev.get("tool_name"), ev.get("tool_input") or {}
    if tool == "Skill" and "html-plan" in json.dumps(inp):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": name, "additionalContext": rule()}}))
    elif tool == "Bash" and re.search(r"html-plan\S*/pack\.mjs", inp.get("command", "")):
        plan = find_plan(inp["command"], ev.get("cwd", "."))
        if not plan or not os.path.isfile(plan):
            return
        bad = problems(open(plan, encoding="utf-8").read())
        if bad:
            print(json.dumps({
                "decision": "block",
                "reason": f"Goal Verification check failed for {plan}: " + "; ".join(bad)
                + ". Fix the section, then run pack.mjs again.\n\n" + rule(),
            }))


if __name__ == "__main__":
    main()
