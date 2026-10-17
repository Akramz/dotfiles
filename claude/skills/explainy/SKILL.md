---
name: explainy
description: Use when the user asks to explain something like they know nothing about it — a diff, the whole repo, or part of the code. Produces an HTML artifact with big pictures and very few words, aimed at a total beginner. With no argument, explains the whole repository. With `diff`, explains the current change. Otherwise the argument names the focus (a file, directory, or plain-language topic).
---

# Explainy

Explain the topic to someone who has never coded and knows nothing about this domain. No jargon, no code shown, no assumed background.

Scope, from the argument:

- **No argument**: what does this repository do, in the real world?
- **`diff`**: what changed, in plain terms — what could you do before that's different now?
- **Anything else**: treat it as the focus (a file, directory, or plain-language topic) and explain just that.

Read the relevant code first so the explanation is accurate, then throw the code details away — the reader never sees them.

## The artifact

- One or two big, simple pictures (a diagram, an icon row, a before/after) carry the explanation. Text is captions, not paragraphs.
- Favor everyday analogies over technical terms. If you must name a technical thing, explain it in one plain clause right next to it.
- Short sentences. Big text. Lots of whitespace. Nothing to scroll through and read like an essay.
