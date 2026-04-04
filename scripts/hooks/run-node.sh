#!/usr/bin/env bash
# Finds node via mise, nvm, fnm, volta, or system PATH — then delegates.
# Silently exits 0 if node cannot be found anywhere.

set -euo pipefail

# mise
if command -v mise &>/dev/null; then
  exec mise exec node -- node "$@"
fi

# nvm
if [ -n "${NVM_DIR:-}" ] && [ -f "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  source "$NVM_DIR/nvm.sh" --no-use
  exec nvm exec node "$@" 2>/dev/null
fi

# fnm
if command -v fnm &>/dev/null; then
  eval "$(fnm env)"
  exec node "$@"
fi

# volta
if command -v volta &>/dev/null; then
  exec volta run node "$@"
fi

# Fallback: hope it's on PATH; exit 0 if not found
exec node "$@" 2>/dev/null || exit 0
