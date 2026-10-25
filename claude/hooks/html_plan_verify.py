#!/usr/bin/env python3
# Adds a "Goal Verification" section to every /html-plan plan, without forking the plugin.
# UserPromptExpansion / PostToolUse(Skill): inject the rule. PostToolUse(Bash pack.mjs): reject plans without it.
import json
import os
import re
import shlex
import sys

RULE = """Rule from the user for /html-plan: every plan must have a Goal Verification section.

- Add `<doc-claim aux="verify">` after `aux="shared"` and before `aux="scope"`.
- Its first child is `<p><b>Goal Verification</b> · one sentence that says what proves the work is correct and done.</p>`
- Its exhibit is `<doc-draft id="verify" label="Goal Verification">` with the text inside `<script type="text/plain">`. The reader can edit this text, and the edit comes back as a diff.
- In the draft, explain how you will verify that the work is correct: the core logic, not a list of commands. For each level-1 claim, say what you will check, what result proves the claim, and why a wrong implementation would fail that check. Mention a command or test only to support that logic. Read the repo first so the logic fits how the project really runs.
- Write the draft in natural, simple American English, not STE. It is for the user to read and edit.
- pack.mjs does not count `doc-draft` as an exhibit, so it warns "claim verify: nothing under it". Accept that one warning. Do not add a second exhibit.
- If the user gave a way to verify, use it and quote it in the draft. If not, write your best guess and add a `<doc-note tone="warn">` under the draft that says it is a guess.
- If there is a real fork in how to verify (for example, a new test or a manual check), add one `doc-ask` after the draft. It counts toward the 2 to 5 decisions.
- In the hand-over line, ask the user to read the Goal Verification section.
- After the user responds, apply the edits and comments on that section. After you build, verify the work the way the section says and report what you found for each claim."""


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
            print(json.dumps({"hookSpecificOutput": {"hookEventName": name, "additionalContext": RULE}}))
        return
    if name != "PostToolUse":
        return
    tool, inp = ev.get("tool_name"), ev.get("tool_input") or {}
    if tool == "Skill" and "html-plan" in json.dumps(inp):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": name, "additionalContext": RULE}}))
    elif tool == "Bash" and re.search(r"html-plan\S*/pack\.mjs", inp.get("command", "")):
        plan = find_plan(inp["command"], ev.get("cwd", "."))
        if not plan or not os.path.isfile(plan):
            return
        bad = problems(open(plan, encoding="utf-8").read())
        if bad:
            print(json.dumps({
                "decision": "block",
                "reason": f"Goal Verification check failed for {plan}: " + "; ".join(bad)
                + ". Fix the section, then run pack.mjs again.\n\n" + RULE,
            }))


if __name__ == "__main__":
    main()
