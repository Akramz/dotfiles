Rule from the user for /html-plan: every plan must have a Goal Verification section.

- Add `<doc-claim aux="verify">` after `aux="shared"` and before `aux="scope"`.
- Its first child is `<p><b>Goal Verification</b> · one sentence that says what proves the work is correct and done.</p>`
- Its exhibit is `<doc-draft id="verify" label="Goal Verification">` with the text inside `<script type="text/plain">`. The reader can edit this text, and the edit comes back as a diff.
- In the draft, write one short paragraph: the method by which you will know that the ultimate goal of the request is achieved. Describe the goal, not each claim. Mention a command or test only if it is part of that method. Read the repo first so the method fits how the project really runs.
- Write the draft in natural, simple, easy-to-understand American English, not STE. It is for the user to read and edit.
- pack.mjs does not count `doc-draft` as an exhibit, so it warns "claim verify: nothing under it". Accept that one warning. Do not add a second exhibit.
- If the user gave a way to verify, use it and quote it in the draft. If not, write your best guess and add a `<doc-note tone="warn">` under the draft that says it is a guess.
- If there is a real fork in how to verify (for example, a new test or a manual check), add one `doc-ask` after the draft. It counts toward the 2 to 5 decisions.
- In the hand-over line, ask the user to read the Goal Verification section.
- After the user responds, apply the edits and comments on that section. After you build, verify the work the way the section says and report whether the goal is achieved.
