---
name: explain
description: Use when the user asks to explain the codebase, a subsystem, a file or directory, or a code change/diff/branch/PR. Produces a single self-contained, interactive HTML diagram — no separate write-up, covering concepts and architecture rather than a code walkthrough. With no argument, diagrams the whole repository. With `diff`, diagrams the system after the current change. Otherwise the argument names the focus (a file, directory, subsystem, or plain-language description of what to explain).
---

# Explain

Build one interactive diagram of the system, scoped by the argument:

- **No argument**: map the whole repository.
- **`diff`**: diagram the system *after* the current change (working diff, branch, or PR the user names). Show what the change does to the system and why — not a code walkthrough.
- **Anything else**: treat it as a focus — a file, directory, subsystem, or plain-language description — and draw the rest of the system only as far as it takes to place that focus. Focused nodes stand out; their surroundings stay muted.

The page is the diagram. Everything else is a legend or a panel the diagram opens. No separate write-up, no prose section, no summary paragraph below the figure.

**Explain the ideas, not the code.** Do not paste diffs or walk through files one by one. The reader wants to know what the system does and why, at the level they'd want when reviewing the design rather than the implementation. Do not use function, module, or file names as labels — describe components and responsibilities in plain simple language.

## Read the code first

Every box and every arrow comes from code you read. A diagram that looks right but gets the data flow wrong is worse than none, because the reader will trust it.

- Start with what the system declares about itself: entry points, build and dependency manifests, config, CI, compose and infra files, route or CLI registries, the schema or migrations.
- Trace the real paths by following calls, imports, and I/O. Never infer a connection from a name.
- Draw anything outside the repo — a database, a queue, a cloud API, another service — as an external node.
- On a large repo, send parallel `Explore` subagents at separate subsystems, then reconcile their answers yourself.
- Treat READMEs and design docs as claims to check. When a doc and the code disagree, believe the code and say so on the page.
- For `diff` mode: read the actual diff (working tree, branch vs. main, or PR) to find what changed, then read enough of the surrounding system to place it correctly.

## The diagram

**Layout.** Absolutely-positioned `div` nodes in a `position: relative` container, with a `position: absolute; inset: 0` SVG overlay for the edges. Decide the grid up front: columns are layers (entry → orchestration → domain → storage → external), rows are components within a layer. Compute pixel coordinates from that grid so nothing overlaps, and anchor edges to node ports rather than node centers.

**Boxes.** Aim for 8–20 nodes that fit one screen. Collapse a busy area into one node with a note instead of drawing thirty. Wrap subsystems in labeled containers.

- In `diff` mode: give new or changed components a distinct look (color, border, badge) from pre-existing ones, and say so in a legend.

**Edges carry real data.** Label them with example payloads and the mechanism, not type names: `POST /ingest {tile_id: "32TNS", bands: [...]}` beats `Request`. Give synchronous calls, queued messages, and shared-storage reads distinct line styles, and explain those in a legend.

**Interactions.**

- Hover a node: highlight its edges and neighbors, dim everything else.
- Click a node: open a side panel with what it does in two or three sentences, the files it lives in, what it owns, what it reads and writes, and how it fails or changed.
- Flow stepper: one button per key flow — a request lifecycle, the main data path, startup, the error path — that walks the path a hop at a time, lighting the current edge and showing that hop's data.
- In `diff` mode: add a before/after toggle when the change reshapes the architecture.

Name the boxes for what each component does. Put the real file paths in the side panel, so the reader can jump straight to the code.

## Format

- One self-contained HTML file: CSS and JavaScript inline, no CDN, no network. It has to open from disk offline. Hand-author the SVG; do not reach for a diagramming library.
- Save it outside the repository, dated first so the files sort by time: `/tmp/<YYYY-MM-DD>-explain-<repo-or-focus-or-diff>.html`. Open it and tell the user the path.
- No ASCII diagrams, no markdown report. Use HTML, CSS, and SVG for the figure, HTML lists for legends.
- Basic responsive styling. Readable on a phone, though the diagram may scroll sideways.
- Write plainly and actively.
