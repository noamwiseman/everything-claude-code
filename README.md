# Embedded Claude Code — Base Toolkit

![C](https://img.shields.io/badge/-C-A8B9CC?logo=c&logoColor=white)
![C++](https://img.shields.io/badge/-C++-00599C?logo=cplusplus&logoColor=white)
![Python](https://img.shields.io/badge/-Python-3776AB?logo=python&logoColor=white)
![Shell](https://img.shields.io/badge/-Shell-4EAA25?logo=gnu-bash&logoColor=white)
![Markdown](https://img.shields.io/badge/-Markdown-000000?logo=markdown&logoColor=white)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

**A base toolkit for embedded software engineers using Claude Code.** Production-ready agents, skills, hooks, commands, and rules tuned for firmware, RTOS, bare-metal, and systems-level development.

Built on [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) — the original agent harness performance system. This fork strips the web-first defaults and adds embedded-first ones: C/C++ rules for bare-metal, RTOS-aware patterns, and agents that understand the embedded development lifecycle.

Works with **Claude Code**.

---

## Quick Start

### Step 1: Install the Plugin

```bash
# Add marketplace
/plugin marketplace add noamwiseman/everything-claude-code

# Install plugin
/plugin install everything-claude-code@everything-claude-code
```

Or add directly to your `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "everything-claude-code": {
      "source": {
        "source": "github",
        "repo": "noamwiseman/everything-claude-code"
      }
    }
  },
  "enabledPlugins": {
    "everything-claude-code@everything-claude-code": true
  }
}
```

### Step 2: Install Rules (Required)

> **Important:** Claude Code plugins cannot distribute `rules` automatically. Install them manually:

```bash
git clone https://github.com/noamwiseman/everything-claude-code.git

# User-level rules (applies to all projects)
mkdir -p ~/.claude/rules
cp -r everything-claude-code/rules/common ~/.claude/rules/
cp -r everything-claude-code/rules/cpp ~/.claude/rules/      # pick your stack

# Or project-level rules (applies to current project only)
mkdir -p .claude/rules
cp -r everything-claude-code/rules/common .claude/rules/
```

Copy whole language directories (e.g. `rules/common`, `rules/cpp`), not individual files, so relative references keep working.

### Step 3: Start Using

```bash
/everything-claude-code:plan "Add DMA transfer handler"
/tdd
/code-review
```

---

## Which Agent Should I Use?

| I want to... | Command / Agent | Agent |
|--------------|-----------------|-------|
| Plan a new feature | `/plan "Add watchdog timer"` | planner |
| Design system architecture | `/plan` + architect | architect |
| Write code with tests first | `/tdd` | tdd-guide |
| Review code I just wrote | `/code-review` | code-reviewer |
| Fix a failing build | `/build-fix` | build-error-resolver |
| Review C++ code | invoke `cpp-reviewer` | cpp-reviewer |
| Review Rust code | invoke `rust-reviewer` | rust-reviewer |
| Find security vulnerabilities | `/security-scan` | security-reviewer |
| Remove dead code | `/refactor-clean` | refactor-cleaner |

---


## Requirements

### Claude Code CLI Version

**Minimum version: v2.1.0 or later**

Check your version:
```bash
claude --version
```

### Hooks Auto-Loading

> **For Contributors:** Do NOT add a `"hooks"` field to `.claude-plugin/plugin.json`. Claude Code v2.1+ automatically loads `hooks/hooks.json` from installed plugins. Declaring it explicitly causes duplicate detection errors.

---

## FAQ

<details>
<summary><b>How do I check which agents/commands are installed?</b></summary>

```bash
/plugin list everything-claude-code@everything-claude-code
```
</details>

<details>
<summary><b>My hooks aren't working / "Duplicate hooks file" errors</b></summary>

Do NOT add a `"hooks"` field to `.claude-plugin/plugin.json`. Claude Code v2.1+ auto-loads hooks. See the Requirements section above.
</details>

<details>
<summary><b>Can I use only some components?</b></summary>

Clone the repo and manually copy the directories you want into your `~/.claude/` directory.
</details>

---

## Running Tests

```bash
node tests/run-all.js

# Individual test files
node tests/lib/utils.test.js
node tests/hooks/hooks.test.js
```

---

## TODO

### Commands (Missing)

- [ ] `/debug` — Structured debugging workflow: reproduce, isolate, fix, verify
- [ ] `/perf-review` — Performance review: hot paths, allocations, stack usage
- [ ] `/changelog` — Generate changelog from conventional commits

### Agents (Missing)

- [ ] `embedded-reviewer.md` — Embedded C/C++ review (MISRA, memory safety, hardware boundaries)
- [ ] `embedded-build-resolver.md` — Cross-compile and linker error resolution
- [ ] `rtos-reviewer.md` — RTOS task/ISR/scheduling review (FreeRTOS, Zephyr)

### Skills (Missing)

- [ ] `embedded-patterns/` — Bare-metal C patterns, ISRs, memory-mapped registers
- [ ] `rtos-patterns/` — FreeRTOS/Zephyr task design, queues, semaphores
- [ ] `embedded-testing/` — Unity/Ceedling TDD for embedded C
- [ ] `misra-guidelines/` — MISRA-C:2012 rules and static analysis

### Rules

- [ ] Fix rules installation (plugins can't distribute rules automatically)
- [ ] `embedded/` — Embedded C/C++ style and safety rules

### Hooks

- [ ] `memory-persistence/` — Session lifecycle hooks
- [ ] Session usage notification — macOS notification when session limit resets after 95%+ daily usage
- [ ] Safe delete hook — intercept `rm` commands and route through macOS `trash`

### Tests

- [ ] Fix existing test suite (`node tests/run-all.js`)

### Other

- [ ] Hardware-in-the-loop testing strategies
- [ ] Cross-compiler toolchain support (ARM GCC, IAR, LLVM/Clang for embedded)
- [ ] HAL abstraction patterns and peripheral driver skills
- [ ] Linker script and memory map analysis agents
- [ ] Embedded CI/CD pipeline patterns (build, flash, test on target)
- [ ] Power management and low-power mode patterns

---

## License

MIT — Use freely, modify as needed, contribute back if you can.

Based on [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) by Affaan Mustafa.
