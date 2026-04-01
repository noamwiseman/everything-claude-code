---
name: skill-comply
description: Visualize whether skills, rules, and agent definitions are actually followed — auto-generates scenarios at 3 prompt strictness levels, runs agents, classifies behavioral sequences, and reports compliance rates with full tool call timelines
origin: ECC
tools: Read, Bash
---

# skill-comply: Automated Compliance Measurement

Measures whether coding agents actually follow skills, rules, or agent definitions by:
1. Auto-generating expected behavioral sequences (specs) from any .md file
2. Auto-generating scenarios with decreasing prompt strictness (supportive → neutral → competing)
3. Running `claude -p` and capturing tool call traces via stream-json
4. Classifying tool calls against spec steps using LLM (not regex)
5. Checking temporal ordering deterministically
6. Generating self-contained reports with spec, prompts, and timelines

## Prerequisites

The following must be available before running skill-comply:

| Dependency | Purpose | Install |
|------------|---------|---------|
| **Python >=3.9** | Runs the compliance scripts | `brew install python` / system package manager |
| **uv** | Python environment and script runner | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **stream-json** (npm) | Parses Claude's streaming JSON tool call output | `npm install -g stream-json` |

Verify: `uv --version && python3 --version && node -e "require('stream-json')"` should all succeed without errors.

## Supported Targets

- **Skills** (`skills/*/SKILL.md`): Workflow skills like search-first, TDD guides
- **Rules** (`rules/common/*.md`): Mandatory rules like testing.md, security.md, git-workflow.md
- **Agent definitions** (`agents/*.md`): Whether an agent gets invoked when expected (internal workflow verification not yet supported)

## When to Activate

- User runs `/skill-comply <path>`
- User asks "is this rule actually being followed?"
- After adding new rules/skills, to verify agent compliance
- Periodically as part of quality maintenance

## Usage

```bash
# Full run
uv run python -m scripts.run ~/.claude/rules/common/testing.md

# Dry run (no cost, spec + scenarios only)
uv run python -m scripts.run --dry-run ~/.claude/skills/search-first/SKILL.md

# Custom models
uv run python -m scripts.run --gen-model haiku --model sonnet <path>
```

### Fallback: if `claude -p` is unavailable or a run fails

`claude -p` (headless/programmatic mode) is required to capture tool call traces. If it is unavailable:

1. **Check Claude Code version** — `claude --version`. Headless mode was added in Claude Code 1.x; upgrade if needed: `npm install -g @anthropic-ai/claude-code`.
2. **Authentication** — ensure `claude auth status` shows a valid session. Re-authenticate with `claude auth login` if needed.
3. **Dry-run to isolate** — run with `--dry-run` to confirm spec generation works independently of the live model call.
4. **Manual alternative** — open a Claude Code session, paste the scenario prompt manually, and review the tool call sequence in the conversation. Record compliance observations by hand against the expected behavioral sequence in the dry-run output.
5. **Partial failures** — if a single scenario fails mid-run, the other scenarios' results are still valid. Check `~/.claude/skill-comply-runs/` for any partial output files from the failed run.

## Key Concept: Prompt Independence

Measures whether a skill/rule is followed even when the prompt doesn't explicitly support it.

## Report Contents

Reports are self-contained and include:
1. Expected behavioral sequence (auto-generated spec)
2. Scenario prompts (what was asked at each strictness level)
3. Compliance scores per scenario
4. Tool call timelines with LLM classification labels

### Advanced (optional)

For users familiar with hooks, reports also include hook promotion recommendations for steps with low compliance. This is informational — the main value is the compliance visibility itself.
