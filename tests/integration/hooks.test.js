/**
 * Integration tests for hook scripts
 *
 * Tests hook behavior in realistic scenarios with proper input/output handling.
 * Covers: run-with-flags.js dispatcher, governance-capture.js hook.
 *
 * Run with: node tests/integration/hooks.test.js
 */

const assert = require('assert');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');
const REPO_ROOT = path.join(__dirname, '..', '..');

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

function runHookWithInput(scriptPath, input = {}, env = {}, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const proc = spawn('node', [scriptPath], {
      env: { ...process.env, ...env },
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', data => stdout += data);
    proc.stderr.on('data', data => stderr += data);

    proc.stdin.on('error', (err) => {
      if (err.code !== 'EPIPE' && err.code !== 'EOF') reject(err);
    });

    if (input && Object.keys(input).length > 0) {
      proc.stdin.write(JSON.stringify(input));
    }
    proc.stdin.end();

    const timer = setTimeout(() => {
      proc.kill('SIGKILL');
      reject(new Error(`Hook timed out after ${timeoutMs}ms`));
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

function createTestDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'hook-integration-test-'));
}

function cleanupTestDir(testDir) {
  fs.rmSync(testDir, { recursive: true, force: true });
}

// Test suite
async function runTests() {
  console.log('\n=== Hook Integration Tests ===\n');

  let passed = 0;
  let failed = 0;

  const hooksJsonPath = path.join(REPO_ROOT, 'hooks', 'hooks.json');
  const hooks = JSON.parse(fs.readFileSync(hooksJsonPath, 'utf8'));

  // ==========================================
  // Input Format Tests
  // ==========================================
  console.log('Hook Input Format Handling:');

  if (await asyncTest('hooks handle empty stdin gracefully', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {});
    assert.strictEqual(result.code, 0, `Should exit 0, got ${result.code}`);
  })) passed++; else failed++;

  if (await asyncTest('hooks handle malformed JSON input', async () => {
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

  if (await asyncTest('hooks parse valid tool_input correctly', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Bash',
      tool_input: { command: 'echo hello', file_path: '/test/path.js' }
    });
    assert.strictEqual(result.code, 0, 'Should parse and process input');
  })) passed++; else failed++;

  // ==========================================
  // Exit Code Tests
  // ==========================================
  console.log('\nHook Exit Codes:');

  if (await asyncTest('governance-capture exits 0 for clean commands', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Bash',
      tool_input: { command: 'ls -la' }
    });
    assert.strictEqual(result.code, 0, 'Non-blocking hook should exit 0');
  })) passed++; else failed++;

  if (await asyncTest('governance-capture exits 0 even for dangerous commands', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Bash',
      tool_input: { command: 'git push --force' }
    }, { ECC_GOVERNANCE_CAPTURE: '1' });
    assert.strictEqual(result.code, 0, 'Governance capture is non-blocking');
  })) passed++; else failed++;

  // ==========================================
  // Realistic Scenarios
  // ==========================================
  console.log('\nRealistic Scenarios:');

  if (await asyncTest('PreToolUse governance hook processes Write with secrets', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Write',
      tool_input: {
        file_path: '/app/.env',
        content: 'AWS_SECRET_KEY=AKIAIOSFODNN7EXAMPLE\nDB_PASSWORD=hunter2'
      }
    }, { ECC_GOVERNANCE_CAPTURE: '1' });
    assert.strictEqual(result.code, 0, 'Should process without blocking');
  })) passed++; else failed++;

  if (await asyncTest('PostToolUse governance hook processes tool output', async () => {
    const command = hooks.hooks.PostToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: 'Bash',
      tool_input: { command: 'cat /etc/passwd' },
      tool_output: { output: 'root:x:0:0:root:/root:/bin/bash' }
    }, { ECC_GOVERNANCE_CAPTURE: '1' });
    assert.strictEqual(result.code, 0, 'Should process output without blocking');
  })) passed++; else failed++;

  if (await asyncTest('governance hook handles very large input without hanging', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const largeInput = {
      tool_name: 'Write',
      tool_input: { file_path: '/test.js', content: 'x'.repeat(100000) }
    };

    const startTime = Date.now();
    const result = await runHookCommand(command, largeInput);
    const elapsed = Date.now() - startTime;

    assert.strictEqual(result.code, 0, 'Should complete successfully');
    assert.ok(elapsed < 5000, `Should complete in <5s, took ${elapsed}ms`);
  })) passed++; else failed++;

  // ==========================================
  // Error Handling
  // ==========================================
  console.log('\nError Handling:');

  if (await asyncTest('hooks do not crash on unexpected input structure', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      unexpected: { nested: { deeply: 'value' } }
    });
    assert.strictEqual(result.code, 0, 'Should handle unexpected input structure');
  })) passed++; else failed++;

  if (await asyncTest('hooks handle null values in input', async () => {
    const command = hooks.hooks.PreToolUse[0].hooks[0].command;
    const result = await runHookCommand(command, {
      tool_name: null,
      tool_input: null
    });
    assert.strictEqual(result.code, 0, 'Should handle null values gracefully');
  })) passed++; else failed++;

  // ==========================================
  // Timeout Enforcement
  // ==========================================
  console.log('\nTimeout Enforcement:');

  if (await asyncTest('runHookWithInput kills hanging hooks after timeout', async () => {
    const testDir = createTestDir();
    const hangingHookPath = path.join(testDir, 'hanging-hook.js');
    fs.writeFileSync(hangingHookPath, 'setInterval(() => {}, 100);');

    try {
      const startTime = Date.now();
      let error = null;

      try {
        await runHookWithInput(hangingHookPath, {}, {}, 500);
      } catch (err) {
        error = err;
      }

      const elapsed = Date.now() - startTime;
      assert.ok(error, 'Should throw timeout error');
      assert.ok(error.message.includes('timed out'), 'Error should mention timeout');
      assert.ok(elapsed >= 450, `Should wait at least ~500ms, waited ${elapsed}ms`);
      assert.ok(elapsed < 2000, `Should not wait much longer than 500ms, waited ${elapsed}ms`);
    } finally {
      cleanupTestDir(testDir);
    }
  })) passed++; else failed++;

  // Summary
  console.log('\n=== Test Results ===');
  console.log(`Passed: ${passed}`);
  console.log(`Failed: ${failed}`);
  console.log(`Total:  ${passed + failed}\n`);

  process.exit(failed > 0 ? 1 : 0);
}

runTests();
