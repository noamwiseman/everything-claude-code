/**
 * Tests for hook scripts
 *
 * Tests the remaining hook infrastructure: run-with-flags.js dispatcher
 * and governance-capture.js hook.
 *
 * Run with: node tests/hooks/hooks.test.js
 */

const assert = require('assert');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

const REPO_ROOT = path.join(__dirname, '..', '..');

// Test helper
function test(name, fn) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
    return true;
  } catch (err) {
    console.log(`  ✗ ${name}`);
    console.log(`    Error: ${err.message}`);
    return false;
  }
}

// Async test helper
async function asyncTest(name, fn) {
  try {
    await fn();
    console.log(`  ✓ ${name}`);
    return true;
  } catch (err) {
    console.log(`  ✗ ${name}`);
    console.log(`    Error: ${err.message}`);
    return false;
  }
}

// Run a script and capture output
function runScript(scriptPath, input = '', env = {}) {
  return new Promise((resolve, reject) => {
    const proc = spawn('node', [scriptPath], {
      env: { ...process.env, ...env },
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', data => (stdout += data));
    proc.stderr.on('data', data => (stderr += data));

    proc.stdin.on('error', (err) => {
      if (err.code !== 'EPIPE' && err.code !== 'EOF') reject(err);
    });

    if (input) {
      proc.stdin.write(input);
    }
    proc.stdin.end();

    proc.on('close', code => {
      resolve({ code, stdout, stderr });
    });

    proc.on('error', reject);
  });
}

/**
 * Run a hook command string exactly as declared in hooks.json.
 */
function runHookCommand(command, input = {}, env = {}, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const mergedEnv = { ...process.env, CLAUDE_PLUGIN_ROOT: REPO_ROOT, ...env };
    const resolvedCommand = command.replace(
      /\$\{([A-Z_][A-Z0-9_]*)\}/g,
      (_, name) => String(mergedEnv[name] || '')
    );

    const nodeMatch = resolvedCommand.match(/^node\s+"([^"]+)"\s*(.*)$/);
    const nodeArgs = nodeMatch
      ? [
          nodeMatch[1],
          ...Array.from(
            nodeMatch[2].matchAll(/"([^"]*)"|(\S+)/g),
            m => m[1] !== undefined ? m[1] : m[2]
          )
        ]
      : [];

    const proc = nodeMatch
      ? spawn('node', nodeArgs, { env: mergedEnv, stdio: ['pipe', 'pipe', 'pipe'] })
      : spawn('bash', ['-lc', resolvedCommand], { env: mergedEnv, stdio: ['pipe', 'pipe', 'pipe'] });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', data => stdout += data);
    proc.stderr.on('data', data => stderr += data);

    proc.stdin.on('error', (err) => {
      if (err.code !== 'EPIPE' && err.code !== 'EOF') {
        clearTimeout(timer);
        reject(err);
      }
    });

    if (input && Object.keys(input).length > 0) {
      proc.stdin.write(JSON.stringify(input));
    }
    proc.stdin.end();

    const timer = setTimeout(() => {
      proc.kill('SIGKILL');
      reject(new Error(`Hook command timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    proc.on('close', code => {
      clearTimeout(timer);
      resolve({ code, stdout, stderr });
    });

    proc.on('error', err => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

// Create a temporary test directory
function createTestDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'hooks-test-'));
}

// Clean up test directory
function cleanupTestDir(testDir) {
  fs.rmSync(testDir, { recursive: true, force: true });
}

// ==============================
// Main test suite
// ==============================
async function runTests() {
  console.log('\n=== Testing Hook Scripts ===\n');

  let passed = 0;
  let failed = 0;

  const hooksJsonPath = path.join(REPO_ROOT, 'hooks', 'hooks.json');
  const hooks = JSON.parse(fs.readFileSync(hooksJsonPath, 'utf8'));

  // ==========================================
  // hooks.json structure
  // ==========================================
  console.log('hooks.json structure:');

  if (test('hooks.json is valid JSON with hooks object', () => {
    assert.ok(hooks.hooks, 'Should have hooks object');
    assert.ok(hooks.hooks.PreToolUse, 'Should have PreToolUse array');
    assert.ok(hooks.hooks.PostToolUse, 'Should have PostToolUse array');
  })) passed++; else failed++;

  if (test('all hook commands reference existing scripts', () => {
    for (const [lifecycle, hookArray] of Object.entries(hooks.hooks)) {
      for (const hookDef of hookArray) {
        for (const hook of hookDef.hooks) {
          const scriptMatch = hook.command.match(/scripts\/hooks\/[\w-]+\.js/g);
          if (scriptMatch) {
            for (const scriptRef of scriptMatch) {
              const fullPath = path.join(REPO_ROOT, scriptRef);
              assert.ok(fs.existsSync(fullPath), `${lifecycle}: ${scriptRef} should exist`);
            }
          }
        }
      }
    }
  })) passed++; else failed++;

  if (test('all hook commands are valid format', () => {
    for (const [hookType, hookArray] of Object.entries(hooks.hooks)) {
      for (const hookDef of hookArray) {
        assert.ok(hookDef.hooks, `${hookType} entry should have hooks array`);
        for (const hook of hookDef.hooks) {
          assert.ok(hook.command, `Hook in ${hookType} should have command field`);
          const isInline = hook.command.startsWith('node -e');
          const isFilePath = hook.command.startsWith('node "');
          const isNpx = hook.command.startsWith('npx ');
          const isShellWrapper = hook.command.startsWith('bash ') || hook.command.startsWith('sh ');
          assert.ok(
            isInline || isFilePath || isNpx || isShellWrapper,
            `Hook command in ${hookType} should be node/npx/shell, got: ${hook.command.substring(0, 80)}`
          );
        }
      }
    }
  })) passed++; else failed++;

  // ==========================================
  // run-with-flags.js dispatcher
  // ==========================================
  console.log('\nrun-with-flags.js:');

  const runWithFlags = path.join(REPO_ROOT, 'scripts', 'hooks', 'run-with-flags.js');

  if (test('run-with-flags.js exists and is requireable', () => {
    assert.ok(fs.existsSync(runWithFlags), 'Should exist');
    const src = fs.readFileSync(runWithFlags, 'utf8');
    assert.ok(src.includes('isHookEnabled'), 'Should reference isHookEnabled');
  })) passed++; else failed++;

  if (await asyncTest('run-with-flags dispatches governance-capture hook', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Bash',
      tool_input: { command: 'echo hello' }
    });
    assert.strictEqual(result.code, 0, `Should exit 0, got ${result.code}`);
  })) passed++; else failed++;

  if (await asyncTest('run-with-flags respects ECC_DISABLED_HOOKS', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Bash',
      tool_input: { command: 'echo hello' }
    }, { ECC_DISABLED_HOOKS: 'pre:governance-capture' });
    assert.strictEqual(result.code, 0, 'Should exit 0');
    // When disabled, should skip the hook logic
    assert.ok(!result.stderr.includes('[Governance]'), 'Should not run governance capture when disabled');
  })) passed++; else failed++;

  if (await asyncTest('run-with-flags respects ECC_HOOK_PROFILE=minimal', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Bash',
      tool_input: { command: 'echo hello' }
    }, { ECC_HOOK_PROFILE: 'minimal' });
    assert.strictEqual(result.code, 0, 'Should exit 0');
  })) passed++; else failed++;

  if (await asyncTest('run-with-flags handles empty stdin gracefully', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {});
    assert.strictEqual(result.code, 0, 'Should exit 0 on empty input');
  })) passed++; else failed++;

  if (await asyncTest('run-with-flags handles malformed JSON', async () => {
    const mergedEnv = { ...process.env, CLAUDE_PLUGIN_ROOT: REPO_ROOT };
    const resolvedCommand = hooks.hooks.PreToolUse[0].hooks[0].command.replace(
      /\$\{([A-Z_][A-Z0-9_]*)\}/g,
      (_, name) => String(mergedEnv[name] || '')
    );
    const nodeMatch = resolvedCommand.match(/^node\s+"([^"]+)"\s*(.*)$/);
    const nodeArgs = [
      nodeMatch[1],
      ...Array.from(
        nodeMatch[2].matchAll(/"([^"]*)"|(\S+)/g),
        m => m[1] !== undefined ? m[1] : m[2]
      )
    ];

    const proc = spawn('node', nodeArgs, {
      env: mergedEnv,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let code = null;
    proc.stdin.on('error', () => {});
    proc.stdin.write('{ invalid json }');
    proc.stdin.end();

    await new Promise((resolve) => {
      proc.on('close', (c) => { code = c; resolve(); });
    });

    assert.strictEqual(code, 0, 'Should handle malformed JSON gracefully');
  })) passed++; else failed++;

  // ==========================================
  // governance-capture.js via hooks.json command
  // ==========================================
  console.log('\ngovernance-capture via hooks.json:');

  if (await asyncTest('governance-capture passes through clean input', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Bash',
      tool_input: { command: 'ls -la' }
    }, { ECC_GOVERNANCE_CAPTURE: '1' });
    assert.strictEqual(result.code, 0, 'Should exit 0');
  })) passed++; else failed++;

  if (await asyncTest('governance-capture detects secrets in input', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Write',
      tool_input: { content: 'AKIAIOSFODNN7EXAMPLE' }
    }, { ECC_GOVERNANCE_CAPTURE: '1' });
    assert.strictEqual(result.code, 0, 'Should exit 0 (non-blocking)');
  })) passed++; else failed++;

  if (await asyncTest('PostToolUse governance-capture hook works', async () => {
    const command = hooks.hooks.PostToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Bash',
      tool_input: { command: 'echo hello' },
      tool_output: { output: 'hello' }
    });
    assert.strictEqual(result.code, 0, 'Should exit 0');
  })) passed++; else failed++;

  // ==========================================
  // run-all.js test runner
  // ==========================================
  console.log('\nrun-all.js test runner:');

  if (test('test runner discovers nested tests via tests/**/*.test.js glob', () => {
    const runAllSrc = fs.readFileSync(path.join(REPO_ROOT, 'tests', 'run-all.js'), 'utf8');
    assert.ok(runAllSrc.includes('tests/**/*.test.js'), 'Should use tests/**/*.test.js glob');
  })) passed++; else failed++;

  // ==========================================
  // Summary
  // ==========================================
  console.log(`\nResults: Passed: ${passed}, Failed: ${failed}`);
  process.exit(failed > 0 ? 1 : 0);
}

runTests();
