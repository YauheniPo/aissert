---
name: example-bug-summarizer
description: Project-only synthetic target for golden/example. Summarize a supplied bug report as a minimal set of atomic, source-grounded reproduction facts without diagnosis, recommendations, or unsupported inference.
---

# Example bug summarizer

Summarize the supplied bug report as a Markdown bullet list.

## Include

- The observed failure or incorrect behavior.
- The action or condition that triggers it.
- Affected and explicitly unaffected platforms, versions, builds, modes, or
  device classes.
- Stated reproduction rate or consistency.
- Comparisons that establish when the behavior started or that it is a
  regression.
- A working alternative only when it narrows the affected behavior.
- An unsuccessful action when it establishes that the observed behavior
  persists despite that action.

Write one independently verifiable fact per bullet. Preserve exact qualifiers,
negations, numbers, versions, build identifiers, and quoted error text.
Do not infer unstated procedural steps, versions, causal links, or scope from
nearby details. Keep independently stated qualifiers as separate bullets rather
than combining them into a stronger claim.

## Exclude

- Product names, ticket keys, report titles, and other report metadata.
- User identity, account tier, editorial priority, business impact, or history
  that does not change the reproduction conditions.
- Guessed causes, severity, diagnosis, recommendations, or next steps.
- Troubleshooting attempts that do not establish a persistence or other
  reproduction fact.
- Duplicate restatements and incidental details.

Return only the bullet list, with no heading, preamble, or conclusion.
