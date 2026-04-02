# Why Rules Stand Out in the Augmentation Toolbox

## Core Advantages

**Always loaded, zero overhead** — Rules inject directly into context at session start. No tool calls, no invocation, no Claude deciding whether to use them. Hooks need shell execution, skills need to be triggered, MCP needs network calls. Rules are just *there*.

**Deterministic presence** — Every session, every time. Memory depends on Claude deciding what's worth saving. Skills load on demand. Rules are the only mechanism *guaranteed* to be in every conversation.

**Path-scoped lazy loading** — Rules in `.claude/rules/` can target specific file patterns:

```markdown
---
paths:
  - "src/api/**/*.ts"
---
All API endpoints must include input validation.
```

This only loads when Claude reads matching files — giving you precision without bloating every session. No other mechanism offers this granularity.

**Version-controllable and shareable** — Plain markdown checked into git. Your whole team sees the same rules. Compare: auto-memory is Claude-generated and personal, hooks are shell scripts requiring debugging, custom instructions live outside version control.

**Multi-level hierarchy** — Org policy → project CLAUDE.md → user CLAUDE.md → path-specific rules. Each layer overrides the previous. You get org standards + project customizations + personal preferences in one clean system.

**Survives compaction** — After `/compact`, CLAUDE.md is re-read from disk and re-injected fresh. Conversation context gets compressed; rules don't.

## When Rules Win vs. Alternatives

| Need | Best tool | Why not rules? |
|------|-----------|----------------|
| Coding standards, conventions, build commands | **Rules** | — |
| Something that *must* execute every time, no exceptions | **Hooks** | Rules are advisory, not enforced |
| Complex on-demand workflows | **Skills** | Would waste context if always loaded |
| External API integrations | **MCP servers** | Rules can't call external services |
| Blocking dangerous operations org-wide | **Managed settings** | Rules can be overridden by prompts |
| Learned preferences over time | **Auto memory** | Rules require manual authoring |

## The Key Insight

Rules are the **foundation** — everything else is specialized. If you want Claude to consistently follow a guideline across every session without any action from you or Claude, rules are unmatched. The other tools solve problems rules *can't*: hooks for deterministic enforcement, skills for on-demand complexity, MCP for external integrations, memory for emergent learning.

The best practice from the docs: for each line in your CLAUDE.md, ask *"Would removing this cause Claude to make mistakes?"* If not, cut it. Keep rules lean and high-signal — that's what makes them powerful.
