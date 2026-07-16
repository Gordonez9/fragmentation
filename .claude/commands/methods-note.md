Generate a short methods-style note describing what the script/pipeline we just
built or modified does and why, written in the register of a methods section
draft — suitable for reuse later in an OQE proposal, thesis chapter, or paper.

Structure it as:

**Purpose:**
- [1-2 sentences — what question or task this script/pipeline addresses.]

**Approach:**
- [2-4 sentences, plain scientific prose (not code, not bullet-by-bullet
  narration) describing what the pipeline does: inputs, tool(s) used, what is
  computed or extracted, and outputs. Write it the way you'd describe a wet-lab
  protocol's logic, not a code walkthrough.]

**Key parameters/assumptions:**
- [Any thresholds, tool versions, default settings, or assumptions worth
  recording now so they don't have to be reconstructed later — e.g., "interface
  = protofilament-protofilament contacts only" or "PISA queried via REST API,
  not local install."]

**Known limitations:**
- [1-2 sentences — honest limitations of this approach, stated the way you
  would in a paper's limitations section, not hedged or hidden.]

Rules:
- Write in formal scientific prose suitable for direct reuse in a proposal or
  paper draft, not casual explanation.
- Do not include code snippets, file paths, or command-line syntax — this is
  for future-you or a committee member reading about the method, not
  reproducing it line by line.
- Do not overstate certainty — if something is a working assumption rather
  than an established fact, phrase it as such.
- Keep it tight — a few sentences per section, not a full paragraph essay.
