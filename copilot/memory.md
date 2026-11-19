# Memory

Claude Code keeps a memory of past work with me, one folder per project. You share it.

- The folder is `~/.claude/projects/<key>/memory/`. `<key>` is the absolute path of the
  working directory with every character that is not a letter or digit replaced by `-`
  (`/Users/me/projects/my_app` gives `-Users-me-projects-my-app`).
- Before your first reply in a session, read `MEMORY.md` in that folder if it exists. It is
  an index, one line per memory file. Open a memory file when its line bears on the task.
- A memory says what was true when it was written. If it names a file, flag or command,
  check that it still exists before you rely on it.
- Save a memory only for something that would change how you work in later sessions: a
  correction I gave, a standing preference, a pointer I would otherwise have to repeat.
  Not finished work or the state of a task. Update an existing file before adding a new one.
- A memory is one file with one fact, plus one line in `MEMORY.md`
  (`- [Title](file.md) — hook`):

  ```markdown
  ---
  name: <short-kebab-case-slug>
  description: <one line, used to decide if the memory is relevant>
  metadata:
    type: user | feedback | project | reference
  ---

  <the fact; for feedback and project memories add **Why:** and **How to apply:** lines>
  ```
