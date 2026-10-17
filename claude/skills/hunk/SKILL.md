---
name: hunk
description: Open the current repo's working-tree diff in a live hunk pane beside this session. Use when the user runs /hunk or asks to open hunk.
---

# Hunk

```!
if [ -z "$TMUX" ]; then
  echo "Not in tmux. Ask the user to run: hunk diff --watch"
else
  hunk session get --repo . >/dev/null 2>&1 || {
    command tmux split-window -h -c "$PWD" "hunk diff --watch"
    for i in {1..40}; do hunk session get --repo . >/dev/null 2>&1 && break; sleep 0.25; done
    command tmux select-pane -t "$TMUX_PANE"
  }
  echo "hunk is open."
fi
```

The pane is already handled above. Reply in one line and stop, even if the diff
is empty.

The focus hop matters: `split-window -d` leaks hunk's terminal replies into
this pane, where they open the model picker.

## Notes

The user leaves notes in the pane with `c`. When asked, read them with
`hunk session comment list --repo . --type user --json` and reply to all in one
call: `printf '%s' '{"comments":[{"replyTo":"<noteId>","summary":"..."}]}' | hunk session comment apply --repo . --stdin`.
Don't add comments unless asked for a guided review; then follow `$(hunk skill path)`.
