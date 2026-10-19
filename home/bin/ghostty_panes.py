#!/usr/bin/env python3
# ghostty_panes.py N — make the Ghostty quick terminal hold N splits, sized
# evenly: opt+shift+<N>. Ghostty sends ESC[901<N>~ (config/ghostty/config);
# tmux (home/.tmux.conf) or zsh (home/.zshrc) runs this.
# ghostty_panes.py open SESSION... — tp's multi-open; see open_sessions().
#
# The target is ceil(sqrt(N)) equal columns: 4 is 2x2, 6 is 3x2, 9 is 3x3.
# Counts that don't fill the grid leave some columns one pane short
# (3 = 2+1, 7 = 3+2+2). Ghostty's AppleScript lists, splits and closes the
# splits; Accessibility gives their rectangles, in the same depth-first order.
#
# Idle shells close first. A busy pane closes only when more than N panes are
# busy, and Ghostty kills whatever runs there (a tmux session survives its
# client). Idle panes may also be closed and re-split when that is the only
# way to reach the grid. In a normal Ghostty window it works on the current tab.

import fcntl
import getpass
import itertools
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import tempfile

READ_JS = r"""
function run() {
  const g = Application('Ghostty'), se = Application('System Events');
  const fe = se.processes.byName('Ghostty').attributes.byName('AXFocusedUIElement').value();
  if (!fe) throw new Error('no Ghostty split has focus');
  const win = fe.attributes.byName('AXWindow').value();
  // A normal window has a close button. The quick terminal has no title bar,
  // and holds the terminals that no window does.
  let ts, inWindows = new Set();
  if (win.attributes.byName('AXCloseButton').value()) {
    ts = g.frontWindow().selectedTab().terminals;
  } else {
    ts = g.terminals;
    inWindows = new Set(g.windows.terminals.id().flat());
  }
  const ids = ts.id(), titles = ts.name(), wds = ts.workingDirectory();
  const panes = ids.map((id, i) => ({id, title: titles[i], wd: wds[i]}))
    .filter(p => !inWindows.has(p.id));
  // Accessibility lags a moment behind new and closed splits. Picking text
  // areas by their specifier string saves an Apple event per element.
  let areas = [];
  for (let i = 0; i < 30 && areas.length !== panes.length; i++, delay(0.1)) {
    areas = win.entireContents()
      .filter(e => /\.textAreas\.at\(\d+\)$/.test(Automation.getDisplayString(e)));
  }
  if (areas.length !== panes.length)
    throw new Error(`${panes.length} terminals but ${areas.length} text areas`);
  const frame = e => e.attributes.byName('AXFrame').value();
  const focus = frame(fe).join();
  panes.forEach((p, i) => {
    const [x1, y1, x2, y2] = frame(areas[i]);
    p.rect = [x1, y1, x2 - x1, y2 - y1];
    p.focused = [x1, y1, x2, y2].join() === focus;
  });
  return JSON.stringify(panes);
}
"""

APPLY_JS = r"""
function run(argv) {
  const g = Application('Ghostty'), plan = JSON.parse(argv[0]), ids = {};
  const term = id => g.terminals.byId(ids[id] || id);
  for (const [op, id, dir, fresh] of plan.ops) {
    if (op === 'close') g.close(term(id));
    else ids[fresh] = g.split(term(id), {direction: dir}).id();
  }
  g.performAction('equalize_splits', {on: term(plan.focus)});
  g.focus(term(plan.focus));
}
"""


TYPE_JS = r"""
function run(argv) {
  const g = Application('Ghostty');
  for (const [id, text] of JSON.parse(argv[0]))
    g.performAction('text:' + text, {on: g.terminals.byId(id)});
}
"""


def osa(js, *args):
    out = subprocess.run(['osascript', '-l', 'JavaScript', '-', *args], input=js,
                         capture_output=True, text=True)
    if out.returncode:
        sys.exit(f'ghostty_panes: {out.stderr.strip()}')
    return out.stdout.strip()


# A tree is a leaf id (str) or (direction, children): 'h' lays children out
# left to right, 'v' top to bottom. Same-direction chains are flattened.

def build(panes):
    if len(panes) == 1:
        return panes[0]['id']
    for d, a in (('h', 0), ('v', 1)):
        groups, edge = [], -math.inf
        for p in sorted(panes, key=lambda p: p['rect'][a]):
            if p['rect'][a] >= edge - 2:
                groups.append([])
            groups[-1].append(p)
            edge = max(edge, p['rect'][a] + p['rect'][a + 2])
        if len(groups) > 1:
            return (d, tuple(build(g) for g in groups))
    sys.exit('ghostty_panes: splits do not tile the window')


def leaves(t):
    return [t] if isinstance(t, str) else [x for k in t[1] for x in leaves(k)]


def join(d, kids):
    flat = []
    for k in kids:
        flat += k[1] if not isinstance(k, str) and k[0] == d else [k]
    return flat[0] if len(flat) == 1 else (d, tuple(flat))


def close(t, x):
    if isinstance(t, str):
        return None if t == x else t
    return join(t[0], [k for k in (close(k, x) for k in t[1]) if k is not None])


def split(t, x, d, new):
    if t == x:
        return ('h' if d == 'right' else 'v', (x, new))
    if isinstance(t, str):
        return t
    return join(t[0], [split(k, x, d, new) for k in t[1]])


def apply(t, ops):
    for op in ops:
        t = close(t, op[1]) if op[0] == 'close' else split(t, *op[1:])
    return t


# Ghostty's equalize_splits weighs a child by its leaf count along the split
# direction, and by its widest row or column across it.

def weight(t, d):
    if isinstance(t, str):
        return 1
    ws = [weight(k, d) for k in t[1]]
    return sum(ws) if t[0] == d else max(ws)


def sizes(t, w, h, out=None):
    out = {} if out is None else out
    if isinstance(t, str):
        out[t] = (w, h)
        return out
    ws = [weight(k, t[0]) for k in t[1]]
    for k, kw in zip(t[1], ws):
        f = kw / sum(ws)
        sizes(k, w * f, h, out) if t[0] == 'h' else sizes(k, w, h * f, out)
    return out


def shape(n):
    c = math.ceil(math.sqrt(n))
    return (c, *divmod(n, c))


def columns(t):
    kids = [t] if isinstance(t, str) or t[0] == 'v' else t[1]
    cols = []
    for k in kids:
        if isinstance(k, str):
            cols.append([k])
        elif k[0] == 'v' and all(isinstance(x, str) for x in k[1]):
            cols.append(list(k[1]))
        else:
            return None
    return cols


def is_grid(t, n):
    c, q, r = shape(n)
    cols = columns(t)
    return cols is not None and sorted(map(len, cols), reverse=True) == [q + 1] * r + [q] * (c - r)


def grow_grid(t, n, fresh):
    c, q, r = shape(n)
    cols = columns(t)
    if cols is None or len(cols) > c:
        return None
    ops = []
    if len(cols) < c:
        singles = [i for i, col in enumerate(cols) if len(col) == 1]
        if not singles:
            return None
        i = singles[-1]
        for _ in range(c - len(cols)):
            new = next(fresh)
            ops.append(('split', cols[i][0], 'right', new))
            i += 1
            cols.insert(i, [new])
    lens = [len(col) for col in cols]
    if max(lens) > q + 1 or lens.count(q + 1) > r:
        return None
    spare = r - lens.count(q + 1)
    for col in cols:
        want = q + 1 if len(col) == q + 1 else q
        if want == q and spare:
            want, spare = q + 1, spare - 1
        while len(col) < want:
            new = next(fresh)
            ops.append(('split', col[-1], 'down', new))
            col.append(new)
    return ops


def spread(t, w, h):
    s = sizes(t, w, h).values()
    areas = [a * b for a, b in s]
    squareness = sum(abs(math.log(a / b)) for a, b in s) / len(areas)
    return max(areas) / min(areas) - 1, squareness


def grow_greedy(t, n, w, h, fresh):
    ops = []
    while len(leaves(t)) < n:
        new = next(fresh)
        options = [(op, apply(t, [op])) for op in
                   (('split', x, d, new) for x in leaves(t) for d in ('right', 'down'))]
        op, t = min(options, key=lambda o: spread(o[1], w, h))
        ops.append(op)
    return ops


def plan(t, idle, n, w, h):
    panes = leaves(t)
    busy = [x for x in panes if x not in idle][::-1]
    spare = [x for x in panes if x in idle][::-1]
    must = max(0, len(panes) - n)
    options = []
    for busy_out in itertools.combinations(busy, max(0, len(busy) - n)):
        least = max(0, must - len(busy_out))
        for k in range(least, min(len(spare), least + 3) + 1):
            for idle_out in itertools.combinations(spare, k):
                out = busy_out + idle_out
                if len(out) == len(panes):
                    continue
                ops = [('close', x) for x in out]
                kept = apply(t, ops)
                fresh = (f'new{i}' for i in itertools.count())
                grown = grow_grid(kept, n, fresh)
                ops += grown if grown is not None else grow_greedy(kept, n, w, h, fresh)
                final = apply(t, ops)
                options.append(((not is_grid(final, n), spread(final, w, h), k), ops, final))
    _, ops, final = min(options, key=lambda o: o[0])
    return ops, final


# An idle shell titles its pane with the prompt's user@host:dir (oh-my-zsh) or
# the directory, long ones as …/last/three/dirs (Ghostty's shell integration).
# A running command puts its command line there instead.
HOME = os.path.expanduser('~')
PROMPT = f"{getpass.getuser()}@{socket.gethostname().split('.')[0]}:"


def is_idle(p):
    title, wd = p['title'], p['wd'] or ''
    short = '~' + wd[len(HOME):] if wd.startswith(HOME) else wd
    return (title in ('', '👻', short) or title.startswith(PROMPT)
            or (title.startswith('…/') and short.endswith(title[1:])))


def resize(panes, n):
    x0 = min(p['rect'][0] for p in panes)
    y0 = min(p['rect'][1] for p in panes)
    w = max(p['rect'][0] + p['rect'][2] for p in panes) - x0
    h = max(p['rect'][1] + p['rect'][3] for p in panes) - y0
    t = build(panes)
    idle = {p['id'] for p in panes if is_idle(p)}
    ops, final = plan(t, idle, n, w, h)
    kept = leaves(final)
    focused = [p['id'] for p in panes if p['focused']]
    old = set(leaves(t))
    busy = [x for x in kept if x in old and x not in idle]
    focus = next((x for x in focused if x in kept), (busy or kept)[0])
    osa(APPLY_JS, json.dumps({'ops': ops, 'focus': focus}))


def tmux(*args):
    tool = shutil.which('tmux') or '/opt/homebrew/bin/tmux'
    return subprocess.run([tool, *args], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL).stdout


def reading_order(panes):
    rows, top = [], -math.inf
    for p in sorted(panes, key=lambda p: p['rect'][1]):
        if p['rect'][1] > top + 3:
            rows.append([])
            top = p['rect'][1]
        rows[-1].append(p)
    return [p for row in rows for p in sorted(row, key=lambda p: p['rect'][0])]


# Show the sessions in the splits after the focused one, in reading order
# (rows top to bottom, each left to right), adding splits when too few are
# usable. tp opens its first pick in the focused split itself. tmux titles
# each split "<session> <client tty>" (home/.tmux.conf): such a split switches
# its client, an idle shell gets `tmux attach` typed in, other busy splits
# are skipped.
def open_sessions(names):
    clients = set(tmux('list-clients', '-F', '#{client_tty}').split())
    sock = os.environ.get('TMUX', '').split(',')[0]
    attach = f"tmux -S {sock} attach" if sock else 'tmux attach'

    def around(panes, start):
        order = reading_order(panes)
        i = [p['id'] for p in order].index(start)
        return order[:i], order[i + 1:]

    def usable(panes):
        out = []
        for p in panes:
            tty = p['title'].rsplit(' ', 1)[-1]
            if tty in clients or is_idle(p):
                out.append((p, tty if tty in clients else None))
        return out

    panes = json.loads(osa(READ_JS))
    start = next((p['id'] for p in panes if p['focused']), None)
    if start is None:
        sys.exit('ghostty_panes: no Ghostty split has focus')
    targets = usable(around(panes, start)[1])
    if len(targets) < len(names):
        old = {p['id'] for p in panes}
        resize(panes, len(panes) + len(names) - len(targets))
        before, after = around(json.loads(osa(READ_JS)), start)
        # The grid may put new splits before the focused one; use them last.
        targets = usable(after + [p for p in before if p['id'] not in old])
    typed = []
    for name, (p, tty) in zip(names, targets):
        if tty:
            tmux('switch-client', '-c', tty, '-t', f'={name}')
        else:
            typed.append([p['id'], f"\\x15{attach} -t '={name}'\\x0d"])
    if typed:
        osa(TYPE_JS, json.dumps(typed))


def main():
    args = sys.argv[1:]
    if not (args in [[str(n)] for n in range(1, 10)] or (args[:1] == ['open'] and args[1:])):
        sys.exit('usage: ghostty_panes.py N | open SESSION...   (N = 1..9)')
    with open(os.path.join(tempfile.gettempdir(), 'ghostty_panes.lock'), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args[0] == 'open':
            open_sessions(args[1:])
        else:
            resize(json.loads(osa(READ_JS)), int(args[0]))


if __name__ == '__main__':
    main()
