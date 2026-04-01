# Claude Code Hooks

These are **Claude Code hooks** (not git hooks) — shell commands that run automatically in response to Claude tool events.

## Hook Types

Configure all hooks under `hooks` in `~/.claude/settings.json`.

- **PreToolUse**: Runs before a tool executes; can block or modify the call.
  Example — block dangerous `rm -rf` patterns, or run a linter before every `Edit`:
  `{ "event": "PreToolUse", "matcher": "Bash", "command": "node scripts/hooks/validate-bash.js" }`

- **PostToolUse**: Runs after a tool completes; useful for side effects.
  Example — auto-format a file after `Write`, or append every tool call to an audit log:
  `{ "event": "PostToolUse", "matcher": "Write", "command": "node scripts/hooks/auto-format.js" }`

- **Stop**: Runs when the session ends; ideal for final verification steps.
  Example — run the full test suite, or save session state to disk:
  `{ "event": "Stop", "command": "node scripts/hooks/session-end.js" }`

## Auto-Accept Permissions

"Permissions" here refers to the tool-use approval prompts Claude shows before running potentially destructive tools. Use `allowedTools` in `~/.claude/settings.json` to pre-approve specific tools and skip those prompts:

`{ "allowedTools": ["Read", "Grep", "Bash(git status)"] }`

Use with caution:
- Enable for trusted, well-defined plans
- Disable for exploratory work
- Never use the `--dangerously-skip-permissions` flag

## TodoWrite Best Practices

Using TodoWrite externalises the plan so Claude can verify each step against the original instructions before acting — reducing drift on long or multi-step tasks.

Use TodoWrite tool to:
- Track progress on multi-step tasks
- Verify understanding of instructions
- Enable real-time steering
- Show granular implementation steps

Todo list reveals:
- Out of order steps
- Missing items
- Extra unnecessary items
- Wrong granularity
- Misinterpreted requirements
