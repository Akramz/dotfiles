#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
# agent_usage.py [SINCE UNTIL] [-o OUT.png] — one PNG of Claude Code + Copilot CLI
# usage over SINCE..UNTIL (YYYY-MM-DD, inclusive, local time). Default: last Mon–Sat.
# Spend comes from ccusage (it reads both CLIs; Copilot is the metered AIU
# equivalent). Prompts, tools, skills, subagents come from the session logs
# in ~/.claude/projects and ~/.copilot/session-state. Claude Code prunes logs
# older than ~30 days, so older periods come out short.

import argparse, glob, json, os, re, subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HOME = os.path.expanduser('~')
TOOL_NAMES = {'bash': 'Bash', 'read_bash': 'Bash', 'write_bash': 'Bash', 'stop_bash': 'Bash', 'list_bash': 'Bash',
              'view': 'Read', 'edit': 'Edit', 'apply_patch': 'Edit', 'create': 'Write', 'web_fetch': 'WebFetch',
              'web_search': 'WebSearch', 'glob': 'Grep / Glob', 'rg': 'Grep / Glob', 'grep': 'Grep / Glob',
              'Grep': 'Grep / Glob', 'Glob': 'Grep / Glob', 'skill': 'Skill', 'task': 'Agent', 'Task': 'Agent'}


def ccusage(*args):
    cmd = ['npx', '-y', 'ccusage@20.0.44', *args, '--json']
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


def local_day(ts):
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone().date()
    except (ValueError, AttributeError):
        return None


def tool_name(n):
    if n.startswith('mcp__'):
        return n.split('__')[1].removeprefix('plugin_').split('_')[0].removesuffix('-mcp') + ' MCP'
    return TOOL_NAMES.get(n, n)


def first_cwd(path):
    for f in glob.glob(os.path.join(path, '*.jsonl')):
        for line in open(f, errors='ignore'):
            m = re.search(r'"cwd":"([^"]+)"', line)
            if m:
                return m.group(1)
    return None


def project(cwd):
    if not cwd:
        return 'other'
    m = re.match(r'/private/tmp/claude-\d+/(-[^/]+)/', cwd)  # an agent's scratchpad: credit its project
    if m:
        return project(first_cwd(f'{HOME}/.claude/projects/{m.group(1)}'))
    m = re.search(r'resident-\d{4}-\d{2}-\d{2}-([^/]+)', cwd)
    if m:
        return f'researcher: {m.group(1)}'
    m = re.match(re.escape(HOME) + r'/\.cache/([^/]+)/', cwd)
    if m:
        return m.group(1)
    if cwd.rstrip('/') == HOME:
        return 'home (~)'
    if not cwd.startswith(HOME):
        return 'other'
    d = cwd
    while d.startswith(HOME + '/'):
        if os.path.exists(os.path.join(d, '.git')):
            return os.path.basename(d)
        d = os.path.dirname(d)
    return os.path.basename(cwd)


def claude_logs(since, until):
    tools, tools_sub, skills_model, skills_user, prompts = Counter(), Counter(), Counter(), Counter(), Counter()
    sessions, subagents, seen, commands = set(), set(), set(), {}
    cutoff = datetime.combine(since, datetime.min.time()).timestamp()
    for f in glob.glob(f'{HOME}/.claude/projects/**/*.jsonl', recursive=True):
        if os.path.getmtime(f) < cutoff:
            continue
        sub = '/subagents/' in f
        for line in open(f, errors='ignore'):
            if '"tool_use"' not in line and '"type":"user"' not in line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            day = local_day(e.get('timestamp', ''))
            if not day or not since <= day <= until:
                continue
            side = sub or e.get('isSidechain')
            c = (e.get('message') or {}).get('content')
            if e.get('type') == 'assistant' and isinstance(c, list):
                for b in c:
                    if b.get('type') != 'tool_use' or b['id'] in seen:
                        continue
                    seen.add(b['id'])
                    (tools_sub if side else tools)[tool_name(b['name'])] += 1
                    if sub:
                        subagents.add(f)
                    else:
                        sessions.add(e.get('sessionId'))
                    if b['name'] == 'Skill':
                        skills_model[(b.get('input') or {}).get('skill', '?').split(':')[-1]] += 1
            elif e.get('type') == 'user' and not side:
                if e.get('uuid') in seen or e.get('toolUseResult'):
                    continue
                seen.add(e.get('uuid'))
                if e.get('isMeta'):  # a skill's expanded prompt; built-in commands get none
                    if e.get('parentUuid') in commands:
                        skills_user[commands.pop(e['parentUuid'])] += 1
                    continue
                txt = c if isinstance(c, str) else ' '.join(
                    b.get('text', '') for b in c or [] if isinstance(b, dict) and b.get('type') == 'text')
                m = re.search(r'<command-name>/?([^<]+)</command-name>', txt)
                if m:
                    commands[e.get('uuid')] = m.group(1).strip().split(':')[-1]
                elif txt.lstrip()[:1] not in ('', '<'):
                    prompts[day] += 1
    return dict(tools=tools, tools_sub=tools_sub, skills_model=skills_model, skills_user=skills_user,
                prompts=prompts, sessions=len(sessions), subagents=len(subagents))


def copilot_logs(since, until):
    tools, skills, cwd = Counter(), Counter(), {}
    cutoff = datetime.combine(since, datetime.min.time()).timestamp()
    for d in glob.glob(f'{HOME}/.copilot/session-state/*/'):
        f = d + 'events.jsonl'
        if not os.path.exists(f) or os.path.getmtime(f) < cutoff:
            continue
        ws = d + 'workspace.yaml'
        m = re.search(r'^cwd:\s*(.+)$', open(ws).read(), re.M) if os.path.exists(ws) else None
        if m:
            cwd[os.path.basename(d.rstrip('/'))] = m.group(1).strip().strip('"\'')
        for line in open(f, errors='ignore'):
            if '"tool.execution_start"' not in line and '"skill.invoked"' not in line:
                continue
            e = json.loads(line)
            day = local_day(e.get('timestamp', ''))
            if not day or not since <= day <= until:
                continue
            data = e.get('data', {})
            if e['type'] == 'skill.invoked':
                skills[(data.get('name') or '?').split(':')[-1]] += 1
            else:
                n, srv = data.get('toolName') or '?', data.get('mcpServerName')
                tools[TOOL_NAMES.get(n) or (f'{srv} MCP' if srv else n)] += 1
    return dict(tools=tools, skills=skills, cwd=cwd)


def collect(since, until):
    s, u = since.strftime('%Y%m%d'), until.strftime('%Y%m%d')
    with ThreadPoolExecutor() as pool:
        daily = pool.submit(ccusage, 'daily', '--since', s, '--until', u, '--by-agent')
        inst = pool.submit(ccusage, 'claude', 'daily', '--since', s, '--until', u, '--instances')
        sess = pool.submit(ccusage, 'copilot', 'session', '--since', s, '--until', u)
        cl, cp = pool.submit(claude_logs, since, until), pool.submit(copilot_logs, since, until)
    cl, cp = cl.result(), cp.result()
    spend = {'claude': Counter(), 'copilot': Counter()}
    for r in daily.result().get('daily', []):
        for a in r['agents']:
            if a['agent'] in spend:
                spend[a['agent']][date.fromisoformat(r['period'])] += a['totalCost']
    proj = {'claude': Counter(), 'copilot': Counter()}
    for enc, rows in inst.result().get('projects', {}).items():
        proj['claude'][project(first_cwd(f'{HOME}/.claude/projects/{enc}'))] += sum(r['totalCost'] for r in rows)
    sessions = sess.result()['sessions']
    for x in sessions:
        proj['copilot'][project(cp['cwd'].get(x['sessionId']))] += x['totalCost']
    top = max(sessions, key=lambda x: x['totalCost'], default=None)
    biggest = (top['totalCost'], project(cp['cwd'].get(top['sessionId']))) if top else (0, '')
    return spend, proj, cl, cp, biggest


def plot(since, until, out):
    spend, proj, cl, cp, biggest = collect(since, until)
    SURF, INK, INK2, MUTED, GRID, AXIS = '#fcfcfb', '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7'
    BLUE, AQUA, ORANGE, YELLOW = '#2a78d6', '#1baf7a', '#eb6834', '#eda100'
    plt.rcParams.update({'font.family': ['Helvetica Neue', 'Helvetica', 'DejaVu Sans'], 'font.size': 10.5,
                         'text.color': INK, 'axes.labelcolor': INK2, 'xtick.color': MUTED, 'ytick.color': INK2,
                         'axes.edgecolor': AXIS, 'figure.facecolor': SURF, 'axes.facecolor': SURF})
    days = [since + timedelta(i) for i in range((until - since).days + 1)]
    c_cost, p_cost = [spend['claude'][d] for d in days], [spend['copilot'][d] for d in days]
    daily = [a + b for a, b in zip(c_cost, p_cost)]
    tot_c, tot_p, total = sum(c_cost), sum(p_cost), sum(daily)
    all_tools = cl['tools'] + cl['tools_sub'] + cp['tools']
    n_prompts = sum(cl['prompts'].values())

    fig = plt.figure(figsize=(17, 11.5), dpi=220)
    gs = fig.add_gridspec(3, 2, height_ratios=[0.42, 1, 1.05], hspace=0.42, wspace=0.3,
                          left=0.1, right=0.975, top=0.9, bottom=0.05)
    fig.text(0.02, 0.965, f'Coding-agent usage · {since:%a %-d %b} – {until:%a %-d %b %Y}', fontsize=21, weight='bold')
    fig.text(0.02, 0.937, 'Claude Code + GitHub Copilot CLI · cost from ccusage (Copilot = metered AIU '
             'equivalent) · activity from session transcripts', fontsize=11, color=INK2)
    kax = fig.add_axes((0.02, 0.76, 0.955, 0.13))
    kax.axis('off')
    kpis = [(f'${total:,.0f}', 'total spend', f'${total / len(days):,.0f} per day'),
            (f'${tot_c:,.0f}', 'Claude Code', f'{tot_c / total:.0%} of spend' if total else ''),
            (f'${tot_p:,.0f}', 'Copilot CLI', f'largest session ${biggest[0]:,.0f} · {biggest[1]}' if biggest[0] >= 0.5 else ''),
            (f'{n_prompts:,}', 'prompts you typed', f'{cl["sessions"]} Claude Code sessions'),
            (f'{cl["subagents"]}', 'subagent runs', f'{all_tools["Agent"]} Agent calls · {all_tools["Workflow"]} workflows'),
            (f'{sum(all_tools.values()):,}', 'tool calls', f'{sum(cl["tools_sub"].values()):,} by subagents')]
    for i, (big, lab, sub) in enumerate(kpis):
        kax.text(i / len(kpis), 0.62, big, fontsize=27, weight='bold', transform=kax.transAxes)
        kax.text(i / len(kpis), 0.3, lab, fontsize=12, color=INK2, transform=kax.transAxes)
        kax.text(i / len(kpis), 0.05, sub, fontsize=10, color=MUTED, transform=kax.transAxes)

    EG: dict[str, Any] = dict(edgecolor=SURF, linewidth=1.5)
    SPEND = [('Claude Code', BLUE), ('Copilot CLI', ORANGE)]

    def panel(cell, name, legend, axis):
        ax = fig.add_subplot(cell)
        for s in ('top', 'right', 'left' if axis == 'y' else 'bottom'):
            ax.spines[s].set_visible(False)
        ax.grid(axis=axis, color=GRID, lw=0.7)
        ax.set_axisbelow(True)
        ax.tick_params(length=0)
        ax.set_title(name, loc='left', fontsize=14, weight='bold', pad=30)
        ax.legend(handles=[Patch(color=c, label=l) for l, c in legend], loc='lower left', bbox_to_anchor=(0, 1.0),
                  ncol=len(legend), frameon=False, fontsize=10, handlelength=1, handleheight=1,
                  borderaxespad=0.2, labelcolor=INK2)
        return ax

    def hbars(cell, name, counters, legend, fmt):
        ax = panel(cell, name, legend, 'x')
        rows = [k for k, v in sum(counters, Counter()).most_common(12) if v >= 0.5][::-1]
        y, left = range(len(rows)), [0] * len(rows)
        for c, (_, col) in zip(counters, legend):
            vals = [c[r] for r in rows]
            ax.barh(y, vals, 0.62, left=left, color=col, **EG)
            left = [a + b for a, b in zip(left, vals)]
        hi = max(left + [1])
        for i, t in enumerate(left):
            ax.text(t + hi * 0.008, i, fmt(t), va='center', fontsize=10, color=INK2)
        ax.set_yticks(list(y))
        ax.set_yticklabels(rows)
        ax.set_xlim(0, hi * 1.1)
        return ax

    ax = panel(gs[1, 0], 'Spend per day', SPEND, 'y')
    x = range(len(days))
    ax.bar(x, c_cost, 0.62, color=BLUE, **EG)
    ax.bar(x, p_cost, 0.62, bottom=c_cost, color=ORANGE, **EG)
    top = max(daily + [1])
    if len(days) <= 14:
        for i in x:
            ax.text(i, daily[i] + top * 0.015, f'${daily[i]:,.0f}', ha='center', fontsize=10.5, weight='bold')
        ax.set_xticks(list(x))
        ax.set_xticklabels([f'{d:%a %-d}\n{cl["prompts"][d]} prompts' for d in days], color=INK2)
    else:
        step = max(1, len(days) // 10)
        ax.set_xticks(list(x)[::step])
        ax.set_xticklabels([f'{d:%-d %b}' for d in days[::step]], color=INK2)
    pad = max(0, 6 - len(days)) / 2  # keep bars narrow for short periods
    ax.set_xlim(-0.5 - pad, len(days) - 0.5 + pad)
    ax.yaxis.set_major_formatter(lambda v, _: f'${v:,.0f}')
    ax.set_ylim(0, top * 1.12)

    money = lambda t: f'${t:,.0f}'
    hbars(gs[1, 1], 'Spend by project', [proj['claude'], proj['copilot']], SPEND, money) \
        .xaxis.set_major_formatter(lambda v, _: money(v))
    hbars(gs[2, 0], 'Top tools (calls)', [cl['tools'], cl['tools_sub'], cp['tools']],
          [('Claude Code · main session', BLUE), ('Claude Code · subagents', AQUA), ('Copilot CLI', ORANGE)],
          lambda t: f'{t:,}')
    hbars(gs[2, 1], 'Top skills (invocations)', [cl['skills_user'], cl['skills_model'], cp['skills']],
          [('You (/slash command)', YELLOW), ('Claude Code (Skill tool)', BLUE), ('Copilot CLI', ORANGE)],
          lambda t: f'{t:,}')

    fig.savefig(out, dpi=220, facecolor=SURF)
    print(out)
    print(f'total ${total:,.2f} = Claude Code ${tot_c:,.2f} + Copilot ${tot_p:,.2f}; {n_prompts} prompts, '
          f'{cl["sessions"]} sessions, {cl["subagents"]} subagents, {sum(all_tools.values()):,} tool calls')


if __name__ == '__main__':
    today = date.today()
    last_mon = today - timedelta(days=today.weekday() + (0 if today.weekday() == 6 else 7))  # last full Mon–Sat
    p = argparse.ArgumentParser(description='Claude Code + Copilot CLI usage figure')
    p.add_argument('since', nargs='?', type=date.fromisoformat, default=last_mon)
    p.add_argument('until', nargs='?', type=date.fromisoformat, default=last_mon + timedelta(days=5))
    p.add_argument('-o', '--out')
    a = p.parse_args()
    if a.until < a.since:
        p.error('until is before since')
    plot(a.since, a.until, a.out or f'{HOME}/Downloads/agent-usage-{a.since}_to_{a.until}.png')
