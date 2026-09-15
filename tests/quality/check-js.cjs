// Syntax covers every executable JS file; type scope is explicit in tsconfig.json.
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const checks = [];
function run(name, command, args, input) {
  const start = performance.now();
  const result = spawnSync(command, args, {encoding: 'utf8', input});
  const output = (result.stdout || '') + (result.stderr || '') + (result.error?.message || '');
  process.stdout.write(`${name}\n${output}`);
  checks.push({name, command: [command, ...args], exit_code: result.status ?? 1,
    duration_seconds: (performance.now() - start) / 1000, output});
}
function visit(directory) {
  for (const entry of fs.readdirSync(directory, {withFileTypes: true})) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) visit(file);
    else if (/\.(?:js|mjs|cjs)$/.test(file)) {
      const moduleType = file.endsWith('.cjs') || file.endsWith('/theme.js') ? 'commonjs' : 'module';
      run(`syntax:${file}`, process.execPath, ['--check', `--input-type=${moduleType}`], fs.readFileSync(file, 'utf8'));
    }
  }
}
visit('/app/twin_lab/static');
visit('/app/tests');
run('typescript', process.execPath, ['/opt/twin-quality/node_modules/typescript/bin/tsc', '--project', 'tests/quality/tsconfig.json']);
function mustFail(name, args, input, expected) {
  const result = spawnSync(process.execPath, args, {encoding: 'utf8', input});
  const output = (result.stdout || '') + (result.stderr || '');
  const rejected = result.status !== 0 && output.includes(expected);
  checks.push({name, command: [process.execPath, ...args], exit_code: rejected ? 0 : 1,
    expected_rejection: expected, output});
  process.stdout.write(`${name}: ${rejected ? 'PASS' : 'FAIL'}\n`);
}
mustFail('guard:JavaScript syntax', ['--check', '--input-type=module'], 'const = ;', 'SyntaxError');
const temporary = fs.mkdtempSync('/tmp/twin-quality-types-');
const typeFixture = path.join(temporary, 'mismatch.js');
fs.writeFileSync(typeFixture, '/** @type {number} */\nconst count = "wrong";\nexport {count};\n');
mustFail('guard:JavaScript type mismatch', ['/opt/twin-quality/node_modules/typescript/bin/tsc',
  '--allowJs', '--checkJs', '--noEmit', '--target', 'ES2022', '--strict', 'false', typeFixture], undefined, 'TS2322');
const versions = {node: process.version, typescript: require('typescript/package.json').version,
  playwright: require('@playwright/test/package.json').version};
fs.writeFileSync('/quality-output/javascript-results.json', JSON.stringify({checks, versions}, null, 2));
process.exitCode = checks.some(check => check.exit_code !== 0) ? 1 : 0;
