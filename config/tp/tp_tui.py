#!/usr/bin/env python3
"""tp — project-grouped tmux session picker (curses TUI).

Sessions are grouped by the directory they were launched from
(tmux ``#{session_path}``); the project name is that path's leaf dir.

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
import shutil
import subprocess
import sys
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
    __slots__ = ("name", "path", "created", "attached", "is_current")

    def __init__(self, name, path, created, attached, is_current):
        self.name = name
        self.path = path
        self.created = created
        self.attached = attached
        self.is_current = is_current


class Project:
    __slots__ = ("path", "leaf", "display", "sessions")

    def __init__(self, path, leaf):
        self.path = path
        self.leaf = leaf          # raw basename, used for auto-naming
        self.display = leaf       # shown label, may be disambiguated
        self.sessions = []


def load_projects():
    """Read sessions and group them into sorted Project objects."""
    rc, out = tmux("list-sessions", "-F", FIELDS)
    cur = current_session()
    groups = {}
    if rc == 0:
        for line in out.splitlines():
            parts = line.split(SEP)
            if len(parts) < 4:
                continue
            name, path, created, attached = parts[0], parts[1], parts[2], parts[3]
            try:
                created_i = int(created)
            except ValueError:
                created_i = 0
            sess = Session(
                name,
                path,
                created_i,
                attached not in ("", "0"),
                name == cur,
            )
            leaf = os.path.basename(path.rstrip("/")) or path or "/"
            proj = groups.get(path)
            if proj is None:
                proj = Project(path, leaf)
                groups[path] = proj
            proj.sessions.append(sess)

    projects = list(groups.values())
    # Disambiguate identical leaf names by tagging a parent segment.
    dup = Counter(p.leaf for p in projects)
    for p in projects:
        p.sessions.sort(key=lambda s: (s.created, s.name))
        if dup[p.leaf] > 1:
            parent = os.path.basename(os.path.dirname(p.path.rstrip("/")))
            p.display = f"{p.leaf} ({parent})" if parent else p.leaf
        else:
            p.display = p.leaf
    projects.sort(key=lambda p: (p.display.lower(), p.path))
    return projects


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
STATUS_LABEL = {
    "running": "active",
    "waiting": "waiting",
    "done": "idle",
}


class UI:
    def __init__(self, stdscr):
        self.scr = stdscr
        self.projects = load_projects()
        self.query = " ".join(sys.argv[1:])
        self.expanded = {}          # project.path -> bool (manual fold state)
        self.cursor = 0             # index into self.rows
        self.top = 0                # scroll offset
        self.action = None          # result to return
        self.message = ""           # transient status line
        self.rows = []
        self.shown = {}             # project.path -> sessions passing the filter
        self.status = {}            # session name -> 'running'/'waiting'/'done'
        self.rebuild()

    # -- data / layout ----------------------------------------------------- #
    def visible_projects(self):
        """(project, sessions) pairs; a project-name match keeps all its sessions."""
        q = self.query.strip().lower()
        out = []
        for p in self.projects:
            if not q or q in p.display.lower():
                hits = p.sessions
            else:
                hits = [s for s in p.sessions if q in s.name.lower()]
            if hits:
                out.append((p, hits))
        return out

    def is_expanded(self, proj):
        # While filtering, matching projects reveal their sessions by default.
        if self.query.strip():
            return True
        return self.expanded.get(proj.path, False)

    def rebuild(self):
        """Recompute the flat list of visible rows."""
        rows = []
        self.shown = {}
        for p, sessions in self.visible_projects():
            self.shown[p.path] = sessions
            rows.append(("project", p, None))
            if self.is_expanded(p):
                for s in sessions:
                    rows.append(("session", p, s))
        self.rows = rows
        if self.cursor >= len(rows):
            self.cursor = max(0, len(rows) - 1)

    def cur_row(self):
        return self.rows[self.cursor] if self.rows else None

    def existing_names(self):
        return {s.name for p in self.projects for s in p.sessions}

    # -- live status ------------------------------------------------------ #
    def visible_session_names(self):
        return [s.name for kind, _p, s in self.rows if kind == "session"]

    def ensure_status(self):
        """Fill status for any visible session lacking it (cheap after 1st)."""
        for name in self.visible_session_names():
            if name not in self.status:
                self.status[name] = classify(capture_pane(name))

    def poll(self):
        """Timed live refresh: re-read visible session statuses."""
        for name in self.visible_session_names():
            self.status[name] = classify(capture_pane(name))

    def status_label(self, name):
        return STATUS_LABEL.get(self.status.get(name, "done"), "idle")

    # -- rendering --------------------------------------------------------- #
    def render(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        self.ensure_status()

        nsess = sum(len(p.sessions) for p in self.projects)
        title = f" tp  {len(self.projects)} projects / {nsess} sessions"
        self._addstr(0, 0, title[:w])

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
        kind, proj, sess = self.rows[i]
        selected = i == self.cursor
        cursor = ">" if selected else " "
        if kind == "project":
            fold = "-" if self.is_expanded(proj) else "+"
            label = f" {cursor} {fold} {proj.display}"
            self._addstr(y, 0, label[:width])
            count = f"  {len(self.shown[proj.path])}"
            if len(label) < width:
                self._addstr(y, len(label), count[: width - len(label)], curses.A_DIM)
            return

        details = [self.status_label(sess.name)]
        if sess.is_current:
            details.append("you")
        elif sess.attached:
            details.append("attached")
        label = f" {cursor}   {sess.name}"
        self._addstr(y, 0, label[:width])
        suffix = "  " + " / ".join(details)
        if len(label) < width:
            self._addstr(y, len(label), suffix[: width - len(label)], curses.A_DIM)

    def _addstr(self, y, x, s, attr=0):
        try:
            self.scr.addstr(y, x, s, attr)
        except curses.error:
            pass  # bottom-right cell / overflow

    # -- navigation -------------------------------------------------------- #
    def move(self, delta):
        if self.rows:
            self.cursor = max(0, min(len(self.rows) - 1, self.cursor + delta))

    def index_of_project(self, proj):
        for i, (kind, p, _s) in enumerate(self.rows):
            if kind == "project" and p is proj:
                return i
        return self.cursor

    def expand(self):
        row = self.cur_row()
        if not row:
            return
        kind, proj, _s = row
        if kind == "project":
            if not self.is_expanded(proj):
                self.expanded[proj.path] = True
                self.rebuild()
            elif proj.sessions:
                self.move(1)  # already open -> step into first session

    def collapse(self):
        row = self.cur_row()
        if not row:
            return
        kind, proj, _s = row
        if kind == "session":
            self.cursor = self.index_of_project(proj)
            self.expanded[proj.path] = False
            self.rebuild()
        elif kind == "project" and self.is_expanded(proj):
            self.expanded[proj.path] = False
            self.rebuild()

    # -- actions ----------------------------------------------------------- #
    def on_enter(self):
        row = self.cur_row()
        if not row:
            return
        kind, proj, sess = row
        if kind == "session":
            self.action = f"attach{SEP}{sess.name}"
            return "quit"
        names = self.pick_modal(proj, self.shown[proj.path])
        if not names:
            return
        self.action = SEP.join(["attach", *names])
        return "quit"

    def on_new(self):
        row = self.cur_row()
        if not row:
            return
        proj = row[1]
        # lower-cased, e.g. blog-1, blog-2
        base = sanitize(proj.leaf).lower()
        default = next_session_name(base, self.existing_names())
        name = self.text_modal(f"New Copilot CLI session in {proj.display}", default)
        if name is None:
            return
        name = name.strip()
        if not name:
            self.message = "empty name — cancelled"
            return
        if name in self.existing_names():
            self.message = f"session '{name}' already exists"
            return
        self.action = f"create{SEP}{proj.path}{SEP}{name}"
        return "quit"

    def on_delete(self):
        row = self.cur_row()
        if not row:
            return
        kind, proj, sess = row
        if kind == "session":
            if sess.is_current:
                self.message = "can't delete the session tp is running in"
                return
            targets = [sess.name]
            what = f"session '{sess.name}'"
        else:
            targets = [s.name for s in proj.sessions if not s.is_current]
            skipped = len(proj.sessions) - len(targets)
            if not targets:
                self.message = "only the current session here — nothing to delete"
                return
            what = f"project '{proj.display}' — {len(targets)} session(s)"
            if skipped:
                what += " (keeping the current one)"
        if not self.confirm_modal(f"Delete {what}?", targets):
            self.message = "delete cancelled"
            return
        for name in targets:
            tmux("kill-session", "-t", name)
        self.message = f"deleted {len(targets)} session(s)"
        self.refresh_data()

    def refresh_data(self):
        self.projects = load_projects()
        self.rebuild()

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
        """Checklist of sessions. Returns the picked names (the one under the
        cursor when none is ticked), or None if cancelled."""
        picked, cur, top = set(), 0, 0
        while True:
            rows = max(1, self.scr.getmaxyx()[0] - 10)
            top = min(max(top, cur - rows + 1), cur)
            lines = [(f"Open sessions of {proj.display} across splits", 0), ("", 0)]
            for i in range(top, min(len(sessions), top + rows)):
                s = sessions[i]
                mark = "x" if s.name in picked else " "
                lines.append((f"{'>' if i == cur else ' '} [{mark}] {s.name}  {self.status_label(s.name)}",
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
                chosen = [s.name for s in sessions if s.name in picked]
                return chosen or [sessions[cur].name]
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
