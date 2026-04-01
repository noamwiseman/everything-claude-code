---
description: "Scan installed skills for cross-cutting principles and distill them into rule files via a 3-phase workflow"
---

# /rules-distill — Distill Principles from Skills into Rules

Scan all installed skills, surface principles that appear in 2+ skills, and promote them to `rules/` — appending, revising, or creating rule files as needed.

## When to Use

- After `/skill-stocktake` reveals recurring patterns not yet captured as rules
- Monthly rules maintenance (skills drift ahead of rules over time)
- When rules feel incomplete or you keep re-explaining something Claude should already know

## Workflow (3 Phases)

**Phase 1 — Inventory:** Scan all skills under `~/.claude/skills/` and `skills/`, then scan all files under `rules/`. Print counts (skills scanned, rule files, headings indexed) before proceeding.

**Phase 2 — Cross-read and Cluster:** Group skills into thematic clusters and launch a subagent per cluster. Each subagent reads the full rules text and extracts candidates that meet all three criteria: (1) appears in 2+ skills, (2) actionable — writable as "do X" / "don't do Y", (3) not already in rules. After all batches complete, merge and deduplicate across batches. Each candidate gets a verdict: `Append`, `Revise`, `New Section`, `New File`, `Already Covered`, or `Too Specific`.

**Phase 3 — User Review:** Present a summary table and per-candidate details (evidence, violation risk, draft text). User responds with numbers to approve, modify, or skip. **Never write to `rules/` without explicit approval.** Save results to `results.json` in the skill directory.

## Example

**Invocation:** `/rules-distill` with 56 skills and 22 rule files installed.

**Summary table presented to user:**

```
| # | Principle                                        | Verdict     | Target                         | Confidence |
|---|--------------------------------------------------|-------------|--------------------------------|------------|
| 1 | Normalize and type-check LLM output before reuse | New Section | coding-style.md                | high       |
| 2 | Compact context at phase boundaries, not mid-task | Append      | performance.md §Context Window | high       |
| 3 | Define explicit stop conditions for loops         | New Section | coding-style.md                | high       |
```

**After `> Approve 1, 2. Skip 3.`:**

```
Applied: coding-style.md §LLM Output Validation
Applied: performance.md §Context Window Management
Skipped: Iteration Bounds
Results saved to results.json
```

Draft text includes `See skill: <name>` back-references so readers can find the detailed how-to in the originating skill.
