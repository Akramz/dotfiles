import base64, collections, datetime as dt, json, os, subprocess, sys, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VAULT = Path(os.environ.get("REFLECT_VAULT", "~/obsidian_vault")).expanduser()
ROOT = Path(os.environ.get("REFLECT_GIT_ROOT", "~/projects")).expanduser()
TOGGL = "https://api.track.toggl.com"


def run(*args):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True).stdout.strip()


def day(path):
    try:
        return dt.date.fromisoformat(path.stem)
    except ValueError:
        return None


def period(args):
    if len(args) == 2:
        return tuple(dt.date.fromisoformat(a) for a in args)
    # A vault period (2026, 2026-Q3, 2026-Q4-W02) spans its week folders. Each week is the
    # Monday to Sunday that holds most of its notes, so one misdated note does not move it.
    label = tuple(args[0].upper().split("-"))
    mondays = collections.defaultdict(collections.Counter)
    for p in VAULT.glob("Journal/*/Q*/W*/*.md"):
        if p.parts[-4:-1][:len(label)] == label and (d := day(p)):
            mondays[p.parent][d - dt.timedelta(d.weekday())] += 1
    weeks: list[dt.date] = [c.most_common(1)[0][0] for c in mondays.values()]
    if not weeks:
        sys.exit(f"No journal folders match {args[0]}")
    return min(weeks), max(weeks) + dt.timedelta(6)


def request(path, auth, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(TOGGL + path, data=data, headers={**auth, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp), resp.headers.get("X-Next-Row-Number")


def toggl():
    token_file = Path("~/.config/toggl/token").expanduser()
    if not token_file.exists():
        return print("\n## Toggl: no token in ~/.config/toggl/token")
    token = token_file.read_text().strip()
    auth = {"Authorization": "Basic " + base64.b64encode(f"{token}:api_token".encode()).decode()}
    hours, by_project = collections.Counter(), collections.Counter()
    try:
        me = request("/api/v9/me?with_related_data=true", auth)[0]
        wid, projects = me["default_workspace_id"], {p["id"]: p["name"] for p in me["projects"] or []}
        chunk = start
        while chunk <= end:
            chunk_end, row = min(end, chunk + dt.timedelta(365)), None
            while True:
                body = {"start_date": str(chunk), "end_date": str(chunk_end), "page_size": 1000}
                if row:
                    body["first_row_number"] = int(row)
                groups, row = request(f"/reports/api/v3/workspace/{wid}/search/time_entries", auth, body)
                for g in groups:
                    project = projects.get(g["project_id"], "-")
                    h = sum(t["seconds"] for t in g["time_entries"]) / 3600
                    hours[(project, g["description"] or "(no description)")] += h
                    by_project[project] += h
                if not row:
                    break
            chunk = chunk_end + dt.timedelta(1)
    except urllib.error.HTTPError as e:
        return print(f"\n## Toggl: API error {e.code} (the free plan allows ~30 calls an hour)")
    print(f"\n## Toggl: {sum(hours.values()):.1f} h")
    print(" | ".join(f"{p} {h:.1f} h" for p, h in by_project.most_common()))
    for (project, task), h in hours.most_common(60):
        print(f"{h:6.1f} h | {project} | {task}")
    if len(hours) > 60:
        print(f"  … {len(hours) - 60} more tasks, {sum(sorted(hours.values())[:-60]):.1f} h")


def commits():
    author = os.environ.get("REFLECT_GIT_AUTHOR") or run("git", "config", "--global", "user.email")
    found = run("find", ROOT, "-maxdepth", "5", "(", "-name", "node_modules", "-o", "-name", ".venv", ")",
                "-prune", "-o", "-name", ".git", "-print", "-prune")
    repos = [Path(g).parent for g in found.splitlines()]
    log = lambda repo: run("git", "-C", repo, "log", "--all", "-i", f"--author={author}",
                           f"--since={start} 00:00", f"--until={end} 23:59:59",
                           "--date=format-local:%a %m-%d", "--format=%H%x09%ad  %s")
    by_repo, seen = {}, set()
    with ThreadPoolExecutor(8) as pool:
        for repo, out in zip(repos, pool.map(log, repos)):
            lines = []
            for line in out.splitlines():
                sha, text = line.split("\t", 1)
                if sha not in seen:
                    seen.add(sha)
                    lines.append(text)
            if lines:
                by_repo[repo.relative_to(ROOT)] = lines
    print(f"\n## Git: {len(seen)} commits in {len(by_repo)} repos (author ~ {author})")
    for name, lines in sorted(by_repo.items(), key=lambda r: -len(r[1])):
        print(f"\n{name} ({len(lines)})", *lines[:40], sep="\n  ")
        if len(lines) > 40:
            print(f"  … {len(lines) - 40} more")


def vault_files():
    journal = sorted(p for p in VAULT.glob("Journal/*/Q*/W*/*.md") if day(p) and start <= day(p) <= end)
    weekly = sorted(VAULT.glob("Planning/Weekly/*/Q*/W*.md"))
    goals = sorted({VAULT / "Planning/Weekly" / p.parent.relative_to(VAULT / "Journal").with_suffix(".md") for p in journal} & set(weekly))
    reviews = [weekly[weekly.index(g) + 1] for g in goals if weekly.index(g) + 1 < len(weekly)]
    quarters = sorted({p.parts[-4:-2] for p in journal})
    okrs = [VAULT / f"Planning/OKRs/{y}/{q}.md" for y, q in quarters]
    vision = [VAULT / f"Planning/Vision/{y}.md" for y in sorted({y for y, _ in quarters})]
    print(f"\n## Vault files (under {VAULT})")
    for label, paths in [("journal", journal), ("goals", goals), ("review", reviews), ("okrs", okrs), ("vision", vision)]:
        for p in paths:
            if p.exists():
                print(f"{label:8} {p.relative_to(VAULT)}")


args = [a for a in sys.argv[1:] if a != "--no-toggl"]
start, end = period(args)
print(f"{start} to {end}")
if "--no-toggl" not in sys.argv:
    toggl()
commits()
vault_files()
