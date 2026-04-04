# CLAUDE.md

Claude Code plugin for embedded software engineering. Production-grade agents, skills, commands, rules, and hooks tuned for firmware, RTOS, bare-metal, and systems-level C/C++/Rust/Python development.

## Running Tests

```bash
mise exec -- node tests/run-all.js       # full suite
mise exec -- node tests/lib/utils.test.js  # individual file
```

## Architecture

```
agents/      Specialized subagents (code-reviewer, tdd-guide, embedded evaluators, etc.)
commands/    Slash commands users invoke directly
skills/      Domain knowledge and workflow definitions
rules/       Always-on guidelines (common, cpp, python, rust)
hooks/       Trigger-based automations (pre/post tool hooks)
scripts/     Node.js utilities powering hooks, install, and CI
tests/       Test suite mirroring scripts/ structure
mcp-configs/ MCP server configurations
manifests/   Install profiles and component definitions
schemas/     JSON schemas for config validation
```

## Key Commands

### Code Quality
- `/code-review` — Security and quality review of uncommitted changes.
- `/refactor-clean` — Find and remove dead code with test verification at every step.
- `/quality-gate` — Run the full ECC quality pipeline on a file or project.
- `/verify` — Comprehensive verification of current codebase state.

### Testing
- `/tdd` — Test-driven development: scaffold interfaces, write tests first, implement to pass. Targets 80%+ coverage.
- `/test-coverage` — Analyze coverage gaps and generate missing tests.

### Build & Fix
- `/build-fix` — Incrementally fix build and type errors with minimal changes.

### Embedded & Language-Specific
- `/cpp-review`, `/cpp-build`, `/cpp-test` — C++ review, build fix, and TDD (memory safety, concurrency, modern idioms).
- `/rust-review`, `/rust-build`, `/rust-test` — Rust review, build fix, and TDD (ownership, lifetimes, unsafe).
- `/python-review` — Python review (PEP 8, type hints, security, idioms).

### Knowledge & Learning
- `/learn` — Extract reusable patterns from the current session and save as skills.
- `/docs` — Look up current library documentation via Context7.
- `/rules-distill` — Scan skills for cross-cutting principles and distill into rule files.

### Optimization
- `/context-budget` — Analyze context window usage across agents, skills, MCP servers, and rules.
- `/prompt-optimize` — Analyze and optimize a draft prompt (advisory only, does not execute).

## Agents

Agents are invoked by commands or directly by Claude. Each is a markdown file with YAML frontmatter.

| Agent | Purpose |
|-------|---------|
| `architect` | System architecture design |
| `tdd-guide` | Test-driven development enforcement |
| `code-reviewer` | Security and quality review |
| `security-reviewer` | Vulnerability detection |
| `refactor-cleaner` | Dead code removal |
| `doc-updater` | Documentation sync |
| `docs-lookup` | External documentation retrieval |
| `cpp-reviewer` | C++ memory safety, modern idioms, concurrency, embedded patterns |
| `cpp-build-resolver` | C++ build, CMake, and linker error resolution |
| `rust-reviewer` | Ownership, lifetimes, unsafe, idiomatic embedded Rust |
| `rust-build-resolver` | Rust build and dependency resolution |
| `python-reviewer` | PEP 8, type hints, Pythonic patterns |
| `build-error-resolver` | General build and cross-compilation error resolution |
| `embedded-docs-coverage` | Probes Context7 to map embedded SW library documentation coverage and gaps |
| `embedded-prompt-fit` | Evaluates how well prompt-optimize serves embedded SW engineering tasks |

## Rules

Rules are always-on guidelines loaded automatically. Organized by language:

- **common/** — Cross-language: coding style, security, testing, git workflow, performance, patterns, code review, hooks, agents, development workflow.
- **cpp/** — C/C++ coding style, memory safety, embedded patterns, security, testing, hooks.
- **python/** — Python coding style, security, testing, patterns, hooks.
- **rust/** — Rust coding style, ownership patterns, embedded safety, testing, hooks.

## Development Notes

- CommonJS only (no ESM unless `.mjs`). Plain `.js`, no TypeScript.
- File naming: lowercase with hyphens (`python-reviewer.md`, `tdd-workflow.md`).
- Hook scripts: exit 0 on non-critical errors, never block tool execution.
- Blocking hooks must stay fast (<200ms, no network calls).
- New scripts in `scripts/lib/` require a matching test in `tests/lib/`.
- New hooks require at least one integration test in `tests/hooks/`.
- Run `node tests/run-all.js` before committing.
- Conventional commits: `fix:`, `feat:`, `test:`, `docs:`, `chore:`.

## Contributing

- **Agents**: Markdown with YAML frontmatter (`name`, `description`, `tools`, `model`).
- **Skills**: Sections: When to Use, How It Works, Examples.
- **Commands**: Markdown with `description:` frontmatter.
- **Hooks**: JSON with matcher and hooks array.
- **Rules**: Markdown, placed in the appropriate language directory.
