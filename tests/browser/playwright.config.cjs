const {defineConfig} = require('@playwright/test');
const path = require('node:path');
const output = process.env.TWIN_QUALITY_OUTPUT || '/quality-output';

module.exports = defineConfig({
  testDir: __dirname,
  projects: [
    {name: 'legacy', testMatch: ['capture.spec.cjs', 'permission.spec.cjs', 'recovery.spec.cjs', 'refresh.spec.cjs']},
    // Explicit contract transition: legacy clients finish before any v2 plan cutover.
    {name: 'pilot-v2', testMatch: 'pilot-v2.spec.cjs', dependencies: ['legacy']},
    {name: 'linked-plan-v2', testMatch: 'linked-plan-v2.spec.cjs', dependencies: ['pilot-v2']},
  ],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  timeout: 30000,
  expect: {timeout: 5000},
  outputDir: path.join(output, 'browser-artifacts'),
  reporter: [['list'], ['json', {outputFile: path.join(output, 'browser-results.json')}]],
  use: {
    baseURL: 'http://127.0.0.1:8765',
    browserName: 'chromium',
    headless: true,
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    colorScheme: 'light',
  },
});
