#!/usr/bin/env python3
"""tp — project-grouped tmux session picker (curses TUI).

Sessions are grouped by the directory they were launched from
(tmux ``#{session_path}``); the project name is that path's leaf dir.
Projects sit under their host: ``@local`` first (open), then the ssh hosts in
~/.ssh/config (scanned in the background, folded). Enter on a remote session opens
it in a local NAME@HOST window.

Each session row is tagged with its state:
  (active)   the agent is actively working
  (waiting)  it's blocked on a prompt that needs you
  (idle)     idle at the prompt, task finished

Arguments pre-fill the filter (`tp_tui.py general`).

Interaction (always-on type-to-filter):
  type          filter projects and sessions by name
  Backspace     edit the filter query
  Up/Down       move the cursor (also Ctrl-P/Ctrl-N)
  Right         expand the project under the cursor
  Left          collapse it (on a session, jump to & collapse its project)
  Enter         project -> pick sessions to open across Ghostty splits
                session -> attach to it
  Ctrl-A        name a new Copilot CLI session in the project & enter it
  Ctrl-D        delete (project = all its sessions; session = just it), confirmed
  Esc / Ctrl-C  quit

The chosen action is written to ``$TP_RESULT_FILE`` for the shell wrapper:
  attach<TAB><session>[<TAB><session>...]   the first here, the rest in the
                                            next splits (ghostty_panes.py open)
  create<TAB><project_path><TAB><session_name>
Deletes are performed here (with confirmation); the picker stays open.
"""

import curses
import locale
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter

SEP = "\t"
FIELDS = SEP.join(
    ["#{session_name}", "#{session_path}", "#{session_created}", "#{session_attached}"]
)

TMUX = shutil.which("tmux") or "/opt/homebrew/bin/tmux"

# --- live status ---------------------------------------------------------- #
# How a Claude (--permission-mode auto) pane reads, per state. Tune these against
# real `tmux capture-pane -p -t <session>` output if a state is misread.
WORKING_RE = re.compile(r"esc to interrupt", re.I)          # actively generating
# Blocked-needs-you = an interactive numbered selection cursor (`❯ 1.`), which
# every Claude dialog renders (permission / plan-approval / question), plus the
# exact permission phrase. Kept specific so ordinary prose ("would you like…")
# at an idle prompt doesn't read as waiting.
WAITING_RE = re.compile(r"❯[ \t]*\d+\.|Do you want to proceed\?", re.I)
POLL_INTERVAL = 1.0         # seconds between live status refreshes

# --- remote hosts ---------------------------------------------------------- #
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
REMOTE_POLL = 5.0           # seconds between scans of a host that answered
OFFLINE_POLL = 60.0         # ...and of one that did not
# Brew's tmux first: a non-interactive shell on Linux lacks it, and an older
# system tmux there would talk to a different server.
REMOTE_PATH = "PATH=/home/linuxbrew/.linuxbrew/bin:/opt/homebrew/bin:$PATH"
# One line per session (S), then its active pane (P), as classify() reads it.
REMOTE_SCAN = REMOTE_PATH + "\ntmux list-sessions -F '" + FIELDS + "' 2>/dev/null |" + """
while IFS= read -r s; do
  printf 'S\t%s\n' "$s"
  tmux capture-pane -p -t "=${s%%\t*}:" | sed 's/^/P\t/'
done"""


# --------------------------------------------------------------------------- #
# tmux data access
# --------------------------------------------------------------------------- #
def tmux(*args):
    """Run the real tmux binary, returning (returncode, stdout)."""
    try:
        p = subprocess.run(
            [TMUX, *args], capture_output=True, text=True, check=False
        )
        return p.returncode, p.stdout
    except FileNotFoundError:
        return 127, ""


def capture_pane(name):
    """Plain-text snapshot of a session's active pane ('' on failure)."""
    rc, out = tmux("capture-pane", "-p", "-t", name)
    return out if rc == 0 else ""


def classify(text):
    """Map a captured pane to 'running' / 'waiting' / 'done'."""
    if WORKING_RE.search(text):
        return "running"
    # Look at the last lines of *real* content: capture-pane pads the bottom of
    # the pane with blanks, so strip those before taking the tail.
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if WAITING_RE.search("\n".join(lines[-20:])):  # tail = pending prompt
        return "waiting"
    return "done"


def current_session():
    """Name of the session tp is running in, or None when outside tmux."""
    if not os.environ.get("TMUX"):
        return None
    rc, out = tmux("display-message", "-p", "#{session_name}")
    return out.strip() if rc == 0 and out.strip() else None


class Session:
    __slots__ = ("name", "path", "created", "attached", "is_current", "host", "linked")

    def __init__(self, name, path, created, attached, is_current, host=None):
        self.name = name
        self.path = path
        self.created = created
        self.attached = attached
        self.is_current = is_current
        self.host = host          # None for a local session
        self.linked = False       # a remote session with a local NAME@HOST window

    @property
    def key(self):
        """The tmux name here: its own, or that of a remote session's local window."""
        return f"{self.name}@{self.host}" if self.host else self.name


def parse_session(line, cur=None, host=None):
    """Session from one FIELDS line, or None if malformed."""
    parts = line.split(SEP)
    if len(parts) < 4:
        return None
    name, path, created, attached = parts[:4]
    try:
        created = int(created)
    except ValueError:
        created = 0
    return Session(name, path, created, attached not in ("", "0"), name == cur, host)


class Project:
    __slots__ = ("path", "dir", "leaf", "display", "sessions", "host")

    def __init__(self, dirpath, host=None):
        self.path = f"{host}:{dirpath}" if host else dirpath   # as `create` hands it to tp()
        self.dir = dirpath
        self.leaf = os.path.basename(dirpath.rstrip("/")) or dirpath or "/"  # used for auto-naming
        self.display = self.leaf  # shown label, may be disambiguated
        self.sessions = []
        self.host = host

    @property
    def where(self):
        return self.display + (f" on {self.host}" if self.host else "")


def load_projects(remote=()):
    """Read sessions and group them into sorted Project objects. Remote sessions
    replace their local NAME@HOST windows."""
    rc, out = tmux("list-sessions", "-F", FIELDS)
    cur = current_session()
    twins = {s.key: s for s in remote}
    for s in remote:
        s.linked = s.is_current = False
    groups = {}

    def add(sess):
        proj = groups.get((sess.host, sess.path))
        if proj is None:
            proj = groups[(sess.host, sess.path)] = Project(sess.path, sess.host)
        proj.sessions.append(sess)

    for line in out.splitlines() if rc == 0 else ():
        sess = parse_session(line, cur)
        if not sess:
            continue
        twin = twins.get(sess.name)
        if twin:
            twin.linked, twin.is_current = True, sess.is_current
        else:
            add(sess)
    for s in remote:
        add(s)

    projects = list(groups.values())
    # Disambiguate identical leaf names by tagging a parent segment.
    dup = Counter((p.leaf, p.host) for p in projects)
    for p in projects:
        p.sessions.sort(key=lambda s: (s.created, s.name))
        p.display = p.leaf
        if dup[(p.leaf, p.host)] > 1:
            parent = os.path.basename(os.path.dirname(p.dir.rstrip("/")))
            if parent:
                p.display = f"{p.leaf} ({parent})"
    projects.sort(key=lambda p: (p.display.lower(), p.path))
    return projects


def ssh_hosts():
    """Concrete Host names in ~/.ssh/config (not its Includes), one per machine,
    without GitHub aliases."""
    try:
        with open(os.path.expanduser("~/.ssh/config")) as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    names = []
    for line in lines:
        words = line.split()
        if len(words) > 1 and words[0].lower() == "host":
            names += [h for h in words[1:] if not any(c in h for c in "*?!")]
    hosts, seen = [], set()
    for h in names:
        try:
            p = subprocess.run(["ssh", "-G", h], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            continue
        cfg = dict(l.split(" ", 1) for l in p.stdout.splitlines() if " " in l)
        machine = (cfg.get("hostname"), cfg.get("port"), cfg.get("user"))
        if machine[0] in (None, "github.com") or machine in seen:
            continue
        seen.add(machine)
        hosts.append(h)
    return hosts


def ssh_run(host, command, timeout=20):
    """Run command on host; None when ssh itself fails or times out."""
    try:
        p = subprocess.run([*SSH, host, command], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None if p.returncode == 255 else p.stdout


def parse_scan(host, out):
    """(sessions, status by session key) from REMOTE_SCAN output."""
    sessions, panes = [], []
    for line in out.splitlines():
        kind, _, rest = line.partition(SEP)
        if kind == "S" and (sess := parse_session(rest, host=host)):
            sessions.append(sess)
            panes.append([])
        elif kind == "P" and panes:
            panes[-1].append(rest)
    return sessions, {s.key: classify("\n".join(p)) for s, p in zip(sessions, panes)}


def open_remote(sess):
    """Local NAME@HOST window that attaches to sess on its host (as _tp_new_remote
    in ~/.zshrc makes it); returns its name."""
    if not sess.linked:
        inner = "exec tmux new-session -A -s " + shlex.quote(sess.name)
        rcmd = 'exec "$(command -v zsh || echo "$SHELL")" -ilc ' + shlex.quote(inner)
        tmux("new-session", "-d", "-s", sess.key, "-c", os.path.expanduser("~"),
             f"ssh -t {shlex.quote(sess.host)} {shlex.quote(rcmd)} || sleep 5")
    return sess.key


def sanitize(name):
    """Make a tmux-legal session base (no '.', ':' or whitespace)."""
    out = re.sub(r"[.:\s]+", "-", name).strip("-")
    return out or "session"


def next_session_name(base, existing):
    """First free ``base-N`` not already used by any session."""
    n = 1
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


# --------------------------------------------------------------------------- #
# TUI
# --------------------------------------------------------------------------- #
def host_attr():
    """Bold cyan for host rows (bold only without colors)."""
    try:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        return curses.A_BOLD | curses.color_pair(1)
    except curses.error:
        return curses.A_BOLD


def host_label(host):
    return f"@{host or 'local'}"


def row_id(row):
    """Stable key of a row (kind, host or project path, session key)."""
    kind, item, sess = row
    return kind, item if kind == "host" else item.path, sess and sess.key


def parent_id(row):
    kind, item, _sess = row
    if kind == "session":
        return "project", item.path, None
    if kind == "project":
        return "host", item.host, None
    return None


STATUS_LABEL = {
    "running": "active",
    "waiting": "waiting",
    "done": "idle",
}


class UI:
    def __init__(self, stdscr):
        self.scr = stdscr
        self.remote = {}            # host -> (sessions, status) or None if offline
        self.last = {}              # host -> last scan result, to skip unchanged scans
        self.hosts = None           # scanned host names, once read
        self.lock = threading.Lock()
        self.fresh = False          # a scan finished since the last merge
        self.projects = load_projects()
        self.query = " ".join(sys.argv[1:])
        self.open = {}              # row_id -> bool (manual fold state)
        self.count = {}             # row_id -> sessions shown under a host or project row
        self.host_attr = host_attr()
        self.cursor = 0             # index into self.rows
        self.top = 0                # scroll offset
        self.action = None          # result to return
        self.message = ""           # transient status line
        self.rows = []
        self.shown = {}             # project.path -> sessions passing the filter
        self.status = {}            # session key -> 'running'/'waiting'/'done'
        self.rebuild()
        threading.Thread(target=self.start_scans, daemon=True).start()

    # -- remote scans ------------------------------------------------------ #
    def start_scans(self):
        hosts = ssh_hosts()
        with self.lock:
            self.hosts = hosts
        for h in hosts:
            threading.Thread(target=self.scan_loop, args=(h,), daemon=True).start()

    def scan_loop(self, host):
        while True:
            self.rescan(host)
            time.sleep(REMOTE_POLL if self.remote.get(host) else OFFLINE_POLL)

    def rescan(self, host):
        out = ssh_run(host, REMOTE_SCAN)
        result = None if out is None else parse_scan(host, out)
        # Agents redraw constantly; only the session list and their states matter.
        seen = result and ([(s.name, s.path) for s in result[0]], result[1])
        if host in self.remote and seen == self.last.get(host):
            return
        with self.lock:
            self.last[host] = seen
            self.remote[host] = result
            self.fresh = True

    def remote_sessions(self):
        with self.lock:
            self.fresh = False
            found = [r for r in self.remote.values() if r]
        for _sessions, status in found:
            self.status.update(status)
        return [s for sessions, _ in found for s in sessions]

    # -- data / layout ----------------------------------------------------- #
    def visible_projects(self):
        """(project, sessions) pairs; a host- or project-name match keeps all its sessions."""
        q = self.query.strip().lower()
        out = []
        for p in self.projects:
            if not q or q in p.display.lower() or q in host_label(p.host):
                hits = p.sessions
            else:
                hits = [s for s in p.sessions if q in s.name.lower()]
            if hits:
                out.append((p, hits))
        return out

    def is_open(self, rid):
        # While filtering, matches reveal everything; otherwise only @local starts open.
        if self.query.strip():
            return True
        return self.open.get(rid, rid == ("host", None, None))

    def rebuild(self):
        """Recompute the flat list of visible rows: hosts, their projects, their sessions."""
        rows = []
        self.shown = {}
        self.count = {}
        by_host = {}
        for p, sessions in self.visible_projects():
            self.shown[p.path] = sessions
            by_host.setdefault(p.host, []).append(p)
        for host in sorted(by_host, key=lambda h: (h is not None, h or "")):   # @local, then VMs
            hrow = ("host", host, None)
            rows.append(hrow)
            self.count[row_id(hrow)] = sum(len(self.shown[p.path]) for p in by_host[host])
            if not self.is_open(row_id(hrow)):
                continue
            for p in by_host[host]:
                prow = ("project", p, None)
                rows.append(prow)
                self.count[row_id(prow)] = len(self.shown[p.path])
                if self.is_open(row_id(prow)):
                    rows += [("session", p, s) for s in self.shown[p.path]]
        self.rows = rows
        if self.cursor >= len(rows):
            self.cursor = max(0, len(rows) - 1)

    def cur_row(self):
        return self.rows[self.cursor] if self.rows else None

    def existing_names(self, host=None):
        return {s.name for p in self.projects if p.host == host for s in p.sessions}

    # -- live status ------------------------------------------------------ #
    def visible_local_names(self):
        # Remote statuses come from the scans.
        return [s.name for kind, _p, s in self.rows if kind == "session" and not s.host]

    def ensure_status(self):
        """Fill status for any visible session lacking it (cheap after 1st)."""
        for name in self.visible_local_names():
            if name not in self.status:
                self.status[name] = classify(capture_pane(name))

    def poll(self):
        """Timed live refresh: re-read visible session statuses, merge new scans."""
        if self.fresh:
            self.refresh_data()
        for name in self.visible_local_names():
            self.status[name] = classify(capture_pane(name))

    def status_label(self, sess):
        return STATUS_LABEL.get(self.status.get(sess.key, "done"), "idle")

    def hosts_line(self):
        with self.lock:
            if self.hosts is None:
                return "hosts …"
            up = [h for h in self.hosts if self.remote.get(h)]
            down = sum(1 for h in self.hosts if h in self.remote and not self.remote[h])
            waiting = len(self.hosts) - len(up) - down
        parts = up + ([f"{down} offline"] if down else []) + ([f"{waiting} …"] if waiting else [])
        return " ".join(parts)

    # -- rendering --------------------------------------------------------- #
    def render(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        self.ensure_status()

        nsess = sum(len(p.sessions) for p in self.projects)
        title = f" tp  {len(self.projects)} projects / {nsess} sessions"
        self._addstr(0, 0, title[:w])
        hosts = self.hosts_line()
        if hosts and len(title) + 3 < w:
            self._addstr(0, len(title) + 3, hosts[: w - len(title) - 3], curses.A_DIM)

        qline = f" filter  {self.query}_"
        self._addstr(1, 0, qline[:w], curses.A_DIM)

        body_top, body_bot = 3, h - 2
        height = max(1, body_bot - body_top)
        if self.cursor < self.top:
            self.top = self.cursor
        elif self.cursor >= self.top + height:
            self.top = self.cursor - height + 1

        if not self.rows:
            msg = "no matching projects or sessions" if self.query else "no tmux sessions"
            self._addstr(body_top, 3, msg, curses.A_DIM)

        for i in range(self.top, min(len(self.rows), self.top + height)):
            y = body_top + (i - self.top)
            self._render_row(y, i, w)

        hint = " arrows move/fold  enter open  ^A new  ^D delete  type to filter  esc quit"
        self._addstr(h - 1, 0, hint[:w], curses.A_DIM)
        if self.message:
            self._addstr(h - 2, 0, (" " + self.message)[:w])
        scr.refresh()

    def _render_row(self, y, i, width):
        row = self.rows[i]
        kind, proj, sess = row
        cursor = ">" if i == self.cursor else " "
        attr = 0
        if kind == "session":
            details = [self.status_label(sess)]
            if sess.is_current:
                details.append("you")
            elif sess.linked:
                details.append("linked")
            elif sess.attached:
                details.append("attached")
            label, suffix = f" {cursor}       {sess.name}", " / ".join(details)
        else:
            fold = "-" if self.is_open(row_id(row)) else "+"
            name = host_label(proj) if kind == "host" else f"  {proj.display}"
            label, suffix = f" {cursor} {fold} {name}", str(self.count[row_id(row)])
            if kind == "host":
                attr = self.host_attr
        self._addstr(y, 0, label[:width], attr)
        if len(label) < width:
            self._addstr(y, len(label), ("  " + suffix)[: width - len(label)], curses.A_DIM)

    def _addstr(self, y, x, s, attr=0):
        try:
            self.scr.addstr(y, x, s, attr)
        except curses.error:
            pass  # bottom-right cell / overflow

    # -- navigation -------------------------------------------------------- #
    def move(self, delta):
        if self.rows:
            self.cursor = max(0, min(len(self.rows) - 1, self.cursor + delta))

    def index_of(self, rid):
        for i, row in enumerate(self.rows):
            if row_id(row) == rid:
                return i
        return self.cursor

    def expand(self):
        row = self.cur_row()
        if not row or row[0] == "session":
            return
        if not self.is_open(row_id(row)):
            self.open[row_id(row)] = True
            self.rebuild()
        else:
            self.move(1)  # already open -> step into its first child

    def collapse(self):
        """Fold the row under the cursor, or else its parent (and move there)."""
        row = self.cur_row()
        if not row:
            return
        rid = row_id(row)
        if row[0] == "session" or not self.is_open(rid):
            rid = parent_id(row)
            if rid is None:
                return
            self.cursor = self.index_of(rid)
        self.open[rid] = False
        self.rebuild()

    # -- actions ----------------------------------------------------------- #
    def on_enter(self):
        row = self.cur_row()
        if not row:
            return
        kind, proj, sess = row
        if kind == "host":
            self.open[row_id(row)] = not self.is_open(row_id(row))
            self.rebuild()
            return
        if kind == "session":
            picked = [sess]
        else:
            picked = self.pick_modal(proj, self.shown[proj.path])
            if not picked:
                return
        names = [open_remote(s) if s.host else s.name for s in picked]
        self.action = SEP.join(["attach", *names])
        return "quit"

    def on_new(self):
        row = self.cur_row()
        if not row:
            return
        if row[0] == "host":
            self.message = "pick a project for the new session"
            return
        proj = row[1]
        # lower-cased, e.g. blog-1, blog-2
        base = sanitize(proj.leaf).lower()
        default = next_session_name(base, self.existing_names(proj.host))
        name = self.text_modal(f"New Copilot CLI session in {proj.where}", default)
        if name is None:
            return
        name = name.strip()
        if not name:
            self.message = "empty name — cancelled"
            return
        if name in self.existing_names(proj.host):
            self.message = f"session '{name}' already exists"
            return
        self.action = f"create{SEP}{proj.path}{SEP}{name}"
        return "quit"

    def on_delete(self):
        row = self.cur_row()
        if not row:
            return
        kind, proj, sess = row
        if kind == "host":
            self.message = "delete a project or a session, not a whole host"
            return
        if kind == "session":
            if sess.is_current:
                self.message = "can't delete the session tp is running in"
                return
            targets = [sess]
            what = f"session '{sess.name}'"
        else:
            targets = [s for s in proj.sessions if not s.is_current]
            skipped = len(proj.sessions) - len(targets)
            if not targets:
                self.message = "only the current session here — nothing to delete"
                return
            what = f"project '{proj.display}' — {len(targets)} session(s)"
            if skipped:
                what += " (keeping the current one)"
        if proj.host:
            what += f" on {proj.host}"
        if not self.confirm_modal(f"Delete {what}?", [s.key for s in targets]):
            self.message = "delete cancelled"
            return
        for s in targets:
            tmux("kill-session", "-t", "=" + s.key)   # a remote one's local window, if any
        if proj.host:
            kills = "; ".join(f"tmux kill-session -t {shlex.quote('=' + s.name)}" for s in targets)
            if ssh_run(proj.host, f"{REMOTE_PATH}; {kills}") is None:
                self.message = f"could not reach {proj.host}"
                return
            with self.lock:   # the next scan confirms
                sessions, status = self.remote[proj.host]
                self.remote[proj.host] = ([s for s in sessions if s not in targets], status)
        self.message = f"deleted {len(targets)} session(s)"
        self.refresh_data()

    def refresh_data(self):
        row = self.cur_row()
        self.projects = load_projects(self.remote_sessions())
        self.rebuild()
        if row:   # keep the cursor on the same row when scans add rows above it
            self.cursor = self.index_of(row_id(row))

    # -- modals ------------------------------------------------------------ #
    def _popup(self, lines, height, width):
        h, w = self.scr.getmaxyx()
        width = min(width, w - 2)
        height = min(height, h - 2)
        y0 = max(0, (h - height) // 2)
        x0 = max(0, (w - width) // 2)
        win = curses.newwin(height, width, y0, x0)
        win.keypad(True)
        try:
            win.border()
        except curses.error:
            pass
        for i, (text, attr) in enumerate(lines):
            if i + 1 >= height - 1:
                break
            try:
                win.addstr(i + 1, 2, text[: width - 4], attr)
            except curses.error:
                pass
        return win

    def text_modal(self, prompt, default):
        """Editable single-line input. Returns text or None if cancelled."""
        text = default
        while True:
            width = max(len(prompt) + 6, 44)
            win = self._popup(
                [
                    (prompt, 0),
                    ("", 0),
                    ("> " + text, 0),
                    ("", 0),
                    ("enter accept / esc cancel", curses.A_DIM),
                ],
                height=7,
                width=width,
            )
            win.refresh()
            try:
                ch = win.get_wch()
            except (curses.error, KeyboardInterrupt):
                return None
            if isinstance(ch, str):
                if ch in ("\n", "\r"):
                    return text
                if ch == "\x1b":
                    return None
                if ch in ("\x7f", "\x08"):
                    text = text[:-1]
                elif ch == "\x15":  # Ctrl-U clear
                    text = ""
                elif ch.isprintable():
                    text += ch
            elif ch in (curses.KEY_BACKSPACE,):
                text = text[:-1]
            elif ch == curses.KEY_ENTER:
                return text

    def pick_modal(self, proj, sessions):
        """Checklist of sessions. Returns the picked sessions (the one under the
        cursor when none is ticked), or None if cancelled."""
        picked, cur, top = set(), 0, 0
        while True:
            rows = max(1, self.scr.getmaxyx()[0] - 10)
            top = min(max(top, cur - rows + 1), cur)
            lines = [(f"Open sessions of {proj.where} across splits", 0), ("", 0)]
            for i in range(top, min(len(sessions), top + rows)):
                s = sessions[i]
                mark = "x" if s.name in picked else " "
                lines.append((f"{'>' if i == cur else ' '} [{mark}] {s.name}  {self.status_label(s)}",
                              curses.A_BOLD if i == cur else 0))
            lines += [("", 0), ("space pick  a all  enter open  esc cancel", curses.A_DIM)]
            width = max(len(t) for t, _ in lines) + 6
            win = self._popup(lines, height=len(lines) + 2, width=width)
            win.refresh()
            try:
                ch = win.get_wch()
            except (curses.error, KeyboardInterrupt):
                return None
            if ch in ("\x1b", "\x03"):
                return None
            if ch in ("\n", "\r", curses.KEY_ENTER):
                chosen = [s for s in sessions if s.name in picked]
                return chosen or [sessions[cur]]
            if ch == " ":
                picked ^= {sessions[cur].name}
            elif ch == "a":
                everyone = {s.name for s in sessions}
                picked = set() if picked == everyone else everyone
            elif ch in (curses.KEY_UP, "\x10"):
                cur = max(0, cur - 1)
            elif ch in (curses.KEY_DOWN, "\x0e"):
                cur = min(len(sessions) - 1, cur + 1)

    def confirm_modal(self, prompt, targets):
        preview = ", ".join(targets)
        lines = [
            (prompt, 0),
            ("", 0),
            (preview, curses.A_DIM),
            ("", 0),
            ("y confirm / any other key cancel", 0),
        ]
        width = max(len(prompt) + 6, min(len(preview) + 6, 70), 40)
        win = self._popup(lines, height=7, width=width)
        win.refresh()
        try:
            ch = win.get_wch()
        except (curses.error, KeyboardInterrupt):
            return False
        return isinstance(ch, str) and ch in ("y", "Y")

    # -- main loop --------------------------------------------------------- #
    def loop(self):
        while True:
            self.render()
            try:
                ch = self.scr.get_wch()
            except KeyboardInterrupt:
                return None
            except curses.error:
                self.poll()          # idle tick -> live status refresh
                continue
            self.message = ""
            if isinstance(ch, str):
                if ch == "\x1b":            # Esc
                    return None
                if ch == "\x03":            # Ctrl-C
                    return None
                if ch in ("\n", "\r"):
                    if self.on_enter() == "quit":
                        return self.action
                    continue
                if ch == "\x04":            # Ctrl-D
                    self.on_delete()
                    continue
                if ch == "\x01":            # Ctrl-A
                    if self.on_new() == "quit":
                        return self.action
                    continue
                if ch == "\x0e":            # Ctrl-N
                    self.move(1); continue
                if ch == "\x10":            # Ctrl-P
                    self.move(-1); continue
                if ch in ("\x7f", "\x08"):  # Backspace
                    self.query = self.query[:-1]
                    self.rebuild(); continue
                if ch == "\x15":            # Ctrl-U clear query
                    self.query = ""
                    self.rebuild(); continue
                if ch.isprintable():
                    self.query += ch
                    self.cursor = 0
                    self.rebuild(); continue
            else:
                if ch == curses.KEY_UP:
                    self.move(-1)
                elif ch == curses.KEY_DOWN:
                    self.move(1)
                elif ch == curses.KEY_RIGHT:
                    self.expand()
                elif ch == curses.KEY_LEFT:
                    self.collapse()
                elif ch in (curses.KEY_ENTER,):
                    if self.on_enter() == "quit":
                        return self.action
                elif ch == curses.KEY_BACKSPACE:
                    self.query = self.query[:-1]
                    self.rebuild()
                elif ch == curses.KEY_RESIZE:
                    pass


def main(stdscr):
    curses.curs_set(0)
    try:
        curses.set_escdelay(25)
    except (curses.error, AttributeError):
        pass
    stdscr.keypad(True)
    stdscr.timeout(int(POLL_INTERVAL * 1000))   # wake up ~1s to refresh status
    return UI(stdscr).loop()


def run():
    locale.setlocale(locale.LC_ALL, "")
    action = curses.wrapper(main)
    if action:
        dest = os.environ.get("TP_RESULT_FILE")
        if dest:
            with open(dest, "w") as f:
                f.write(action + "\n")
        else:
            sys.stdout.write(action + "\n")


if __name__ == "__main__":
    run()
