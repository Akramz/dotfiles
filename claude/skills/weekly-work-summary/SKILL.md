---
name: weekly-work-summary
description: Summarize the user's Toggl time for a week (Mon–Sat) as bullet points grouped into themes. Use when the user runs /weekly-work-summary or asks what they worked on this week.
---

# Weekly Work Summary

## 1. Fetch the week

The Toggl API token lives in `~/.config/toggl/token`. If it is missing, ask the user to save
it there (Toggl → Profile settings → API Token) and stop.

The week runs Monday 00:00 to Saturday 24:00, local time. By default it is the week that
contains today, so on a Sunday it is the week that just ended. If the user names another
week, pass that week's Monday as `YYYY-MM-DD`.

```
python3 - [MONDAY] <<'EOF'
import base64, collections, datetime as dt, json, os, sys, urllib.parse, urllib.request

token = open(os.path.expanduser("~/.config/toggl/token")).read().strip()
auth = "Basic " + base64.b64encode(f"{token}:api_token".encode()).decode()

def get(path):
    req = urllib.request.Request("https://api.track.toggl.com/api/v9" + path, headers={"Authorization": auth})
    return json.load(urllib.request.urlopen(req, timeout=30))

now = dt.datetime.now().astimezone()
monday = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else now.date() - dt.timedelta(days=now.weekday())
start = dt.datetime.combine(monday, dt.time(), now.tzinfo)
end = start + dt.timedelta(days=6)

entries = get("/me/time_entries?" + urllib.parse.urlencode({"start_date": start.isoformat(), "end_date": end.isoformat()}))
projects = {p["id"]: p["name"] for p in get("/me/projects") or []}

hours = collections.defaultdict(float)
for e in entries:
    secs = e["duration"]
    if secs < 0:
        secs = (now - dt.datetime.fromisoformat(e["start"].replace("Z", "+00:00"))).total_seconds()
    hours[(projects.get(e.get("project_id"), "-"), e.get("description") or "(no description)")] += secs / 3600

print(f"{monday} to {monday + dt.timedelta(days=5)}: {len(entries)} entries, {sum(hours.values()):.1f} h")
for (project, task), h in sorted(hours.items(), key=lambda x: -x[1]):
    print(f"{h:5.2f} h | {project} | {task}")
EOF
```

Each output line gives the hours, the Toggl project and the task.

## 2. Group into themes

Group the tasks into 5–8 themes by what the work was for, not just by Toggl project. For
example, "Setup the GPU machine for the team" filed under `Work` belongs in a team
infrastructure theme. Merge tasks that are near duplicates ("Improve the UX" and "Improve
the website's UX"). Every hour goes into exactly one theme, so the theme totals add up to
the week total.

## 3. Output

Start with one line: the total hours, the date range and the number of entries. Then list
the themes, largest first. Under each theme, list its tasks, largest first, rewritten as
short past-tense phrases. Round to one decimal. An example with made-up numbers:

```
You worked **40.0 h** from Mon Jan 5 to Sat Jan 10, across 60 entries.

- **Team infrastructure: 10.0 h**
  - Set up the shared GPU machine (7.0 h)
  - Wrote the onboarding guide (3.0 h)
- **Planning: 5.0 h**
  - Daily planning (3.0 h)
  - Weekly planning (2.0 h)
```

End with at most one line naming any task whose theme was a close call. Write nothing else.
