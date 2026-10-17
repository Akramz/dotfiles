---
name: minimize
description: Interrogate the whole codebase for unnecessary complexity and weak assumptions, then delete or simplify. Use when the user runs /minimize.
---

# Minimize

Think from first principles about what we're trying to achieve here. Interrogate the whole codebase, not just recent changes:

1. Is anything here unnecessary, overly complicated, or based on weak assumptions? Challenge them.
2. What can be deleted entirely?
3. What can be simplified now that unnecessary pieces are gone?

Then make the changes. Prefer deleting over simplifying, simplifying over optimizing, and optimizing over automating.

It might be done too — you don't HAVE to go and make changes. If it's good, leave it alone.
