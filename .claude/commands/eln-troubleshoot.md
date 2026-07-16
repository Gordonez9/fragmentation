Generate a troubleshooting ELN (electronic lab notebook) entry for this session,
formatted for direct copy-paste into Signals Revvity. This is for documenting a
problem, the diagnostic process, and the outcome — more detailed than a routine
update, since troubleshooting logs are often referenced months later.

Structure it as:

**Date:** [today's date]
**Problem:** [1-2 sentences — what broke, failed, or looked wrong, and how it
was first noticed]

**Diagnostic steps:**
- [Ordered list of what was checked/tried, in the order it happened. Include
  what was ruled out, not just what worked — a negative result is still useful
  record. State the reasoning briefly, e.g. "checked X because Y was suspected."]

**Root cause:**
- [1-3 sentences — what was actually wrong, stated plainly. If not fully
  resolved, say "unresolved — most likely cause is..." rather than guessing
  with false confidence.]

**Fix / Resolution:**
- [What was changed or done to resolve it. Include specific parameters, file
  names, or settings ONLY if they're essential for someone to reproduce the fix
  later — otherwise keep it in plain language.]

**Still open / follow-up needed:**
- [Anything unresolved, any follow-up check needed, or "none" if fully closed.]

Rules:
- Write in plain past-tense declarative sentences, not code blocks, unless a
  specific command or parameter value is essential to reproducing the fix.
- Preserve the actual chronology of what was tried — don't reorder to make the
  process look cleaner or more linear than it was.
- Do not invent steps, numbers, or outcomes that didn't happen in this session.
- If the root cause is still uncertain, say so explicitly rather than presenting
  a guess as confirmed.
- Keep total length reasonable for a notebook entry — thorough but not padded.
