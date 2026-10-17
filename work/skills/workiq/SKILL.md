---
name: workiq
description: Answer questions about the user's Microsoft 365 work data (Teams chats and channels, Outlook mail, meetings and calendar, OneDrive and SharePoint files, colleagues) with the local `workiq` CLI. Use when the user asks what was said, decided, scheduled or shared at work. Work machines only.
---

# Work IQ

Use the `workiq` CLI (Microsoft 365 via Copilot).

## Setup check

If `command -v workiq` fails, say this is not a work machine and stop.

If a command fails on sign-in or the EULA, ask the user to run
`! workiq accept-eula && workiq auth login`, then retry once. An "admin approval" or
AADSTS consent error is a tenant problem: report it and stop.

## Read

- `workiq ask -q "<question>"`: summaries, "what did X say", "who owns Y". Takes 10–60 s.
- `workiq fetch -u "<path>"`: exact lists, e.g. `/me/calendarView?startDateTime=…&endDateTime=…`
  or `/me/messages?$top=10`. Paths start with `/me` or `/users`, with no `/v1.0`, and
  URL-encoded query values.
- `workiq search-paths -f <regex>` and `workiq get-schema -p <path>` find a path or its fields.

## Write

When the user asks you to write an email, create the draft right away; do not show it in chat first.

`create`, `update`, `delete` and `do-action` (e.g. `/me/sendMail`) act as the user. Run one
only when the user asks for that exact write in the current message. Show the command and
its body first. If a write returns nothing or times out, read the target to check before
you retry it.
