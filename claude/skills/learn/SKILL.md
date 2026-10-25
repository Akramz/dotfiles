---
name: learn
description: Teach the user a topic by asking one question at a time and giving the smallest hint when they are stuck, until they answer correctly. Use when the user runs /learn <topic> [number of questions].
---

# Learn

Arguments: a topic, then an optional number of questions (default 5). If the topic is code here, read what each question needs.

Ask N questions, one at a time, in plain chat. Each question is the one that will teach the user the most right now, given the topic and everything they have shown so far.

For each answer:

- If it is correct, say so in a line, add anything they missed, and move on.
- If it is wrong, partly right, or they say they are stuck, give the smallest hint that could unlock it and let them try again, giving a bit more each time.
- If the hints run out, give the answer, ask them to say it back in their own words, and move on. "skip" moves on at once.

Show progress as `Q2/5` on each question.

After the last question, give a short recap: what they knew, what took hints, and the next thing worth learning.
