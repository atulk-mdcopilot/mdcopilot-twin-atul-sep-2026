// Fabricated data only. This suite runs in the isolated quality Compose project.
const {test: base, expect} = require('@playwright/test');
const {randomUUID, createHash} = require('node:crypto');
const BASE = 'http://127.0.0.1:8765';
const test = base.extend({
  browserChecks: [async ({context, page}, use) => {
    const failures = [];
    const expectedErrors = [];
    context.on('request', request => {
      const url = new URL(request.url());
      if (url.origin !== BASE) failures.push(`Unexpected request: ${request.url()}`);
    });
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin !== BASE) return route.abort('blockedbyclient');
      return route.continue();
    });
    page.on('pageerror', error => failures.push(`Uncaught: ${error.message}`));
    page.on('console', message => {
      if (message.type() !== 'error') return;
      const actual = {url: message.location().url, text: message.text()};
      const expected = expectedErrors.find(item => item.remaining > 0 && actual.url === `${BASE}${item.path}` && item.pattern.test(actual.text));
      if (expected) expected.remaining -= 1;
      else {
        failures.push(`Console: ${JSON.stringify(actual)}`);
      }
    });
    await use({allowError: (path, pattern) => expectedErrors.push({path, pattern, remaining: 1})});
    expect(failures, 'No unexpected browser errors or non-loopback requests').toEqual([]);
  }, {auto: true}],
});

async function get(request, path) {
  const response = await request.get(`${BASE}${path}`);
  expect(response.status(), `${path}: ${await response.text()}`).toBe(200);
  return response.json();
}
async function post(request, path, data, expected = 201) {
  const response = await request.post(`${BASE}${path}`, {data, headers: {'X-Twin-Lab': '1'}});
  expect(response.status(), `${path}: ${await response.text()}`).toBe(expected);
  return response.json();
}
function governanceBody(parent = null, status = 'approved') {
  const now = new Date();
  const close = new Date(now.getTime() + 20 * 86400000).toISOString().slice(0, 10);
  const retention = ['response_days', 'after_close_days', 'withdrawal_days', 'export_days',
    'backup_days', 'backup_after_deletion_days', 'permission_after_close_days', 'audit_after_close_days'];
  const controls = ['storage_access_verified', 'device_encryption_verified', 'no_network_verified',
    'lifecycle_verified', 'backup_restore_verified', 'external_copy_control_verified'];
  return {
    request_id: randomUUID(), based_on_governance_id: parent, title: 'Fabricated browser governance', status,
    operator: {legal_name: 'Fabricated test operator', project_contact: 'project@example.invalid',
      privacy_contact: 'privacy@example.invalid', pilot_close_date: close},
    permission: {version: `BROWSER-${randomUUID()}`, text: '  Fabricated browser permission. Café.\nTest fixture only.  '},
    retention: {version: 'BROWSER-RET-1', ...Object.fromEntries(retention.map(key => [key, 7]))},
    owners: ['OWN-PROJ', 'OWN-CLIN', 'OWN-ENG', 'OWN-DATA', 'OWN-PRIV', 'OWN-QA'].map(role_code => ({
      role_code, actor_code: 'STF-BROWSER', person_name: 'Fabricated test actor',
      contact: 'actor@example.invalid', accepted_at: now.toISOString(),
    })),
    controls: {actor_code: 'STF-BROWSER', checked_at: now.toISOString(), evidence: 'Fabricated test evidence only.',
      ...Object.fromEntries(controls.map(key => [key, true]))},
    approved_by_code: 'STF-BROWSER', approval_note: 'Fabricated local fixture, no actual approval.',
  };
}
function planBody(parent, code) {
  return {request_id: randomUUID(), based_on_protocol_id: parent, title: 'Fabricated browser plan',
    owner_code: 'STF-BROWSER', physician_codes: [code, `${code}-OTHER`], consent_statement: '',
    consent_version: '', retention_days: null, backup_owner_code: '', backup_frequency: 'manual_before_changes',
    backup_retention_days: null, notes: 'Fabricated browser assignment plan.'};
}
async function recordReview(request, version, disposition = 'approved') {
  return (await post(request, '/api/case-reviews', {request_id: randomUUID(), version_id: version.version_id,
    reviewer_code: 'STF-BROWSER', reviewed_on: new Date().toISOString().slice(0, 10),
    comments: 'Fabricated browser review only.', disposition,
    supersedes_review_id: version.latest_review?.review_id || null})).review;
}
async function setupHuman(request, {permission = true} = {}) {
  const code = `BROWSER-${randomUUID().slice(0, 8)}`;
  const current = await get(request, '/api/governance');
  const body = governanceBody(current.current?.governance_id || null);
  const governance = (await post(request, '/api/governance', body)).governance;
  const collection = await get(request, '/api/collection');
  const protocol = (await post(request, '/api/protocols', planBody(collection.current?.protocol_id || null, code))).protocol;
  const catalog = await get(request, '/api/catalog');
  const version = catalog.versions.at(-1);
  const review = await recordReview(request, version);
  const assignment = (await post(request, '/api/assignments', {request_id: randomUUID(),
    protocol_id: protocol.protocol_id, physician_code: code, version_id: version.version_id,
    notes: 'Fabricated assignment only.'})).assignment;
  const receipt = permission ? await recordPermission(request, governance, code) : null;
  return {code, body, governance, protocol, version: {...version, latest_review: review}, assignment, receipt};
}
async function recordPermission(request, governance, code, choice = 'agree') {
  return (await post(request, '/api/permissions', {request_id: randomUUID(), governance_id: governance.governance_id,
    physician_code: code, choice})).receipt;
}
async function ready(page) {
  await page.goto('/');
  await expect(page.locator('#case-list button')).toHaveCount(10);
  await expect(page.locator('#capture-mode > [role="status"]')).not.toContainText('Checking');
}
async function openQA(page) {
  await page.locator('[name="qa_acknowledged"]').check();
  const presented = page.waitForResponse(response => response.url().endsWith('/api/presentations') && response.request().method() === 'POST');
  await page.locator('#case-list button').first().click();
  const response = await presented;
  expect(response.status()).toBe(201);
  await expect(page.locator('#next-action')).toBeEnabled();
  return response.json();
}
function values(code = `QA-${randomUUID().slice(0, 8)}`) {
  return {physician_code: code, next_action: '  Fabricated action <em>literal</em>.  ',
    next_information: '  Fabricated observation request.\nSecond line.  ',
    decision_change: '  Fabricated decision change.  ', rationale: 'Fabricated rationale.', confidence: 'moderate'};
}
async function fillResponse(page, answer) {
  for (const [name, value] of Object.entries(answer)) {
    const field = page.locator(`#response-form [name="${name}"]`);
    if (name === 'confidence') await field.selectOption(value || '');
    else if (await field.isEditable()) await field.fill(value);
  }
}
async function saveResponse(page) {
  const saved = page.waitForResponse(response => response.url().endsWith('/api/responses') && response.request().method() === 'POST');
  await page.locator('#save-response').click();
  const response = await saved;
  expect(response.status()).toBe(201);
  await expect(page.locator('#save-status')).toContainText('Saved locally');
  return (await response.json()).response;
}
async function selectHuman(page, fixture) {
  await page.locator('[name="capture_mode"]').selectOption('physician_demo');
  await page.locator('[name="permission_receipt_id"]').selectOption(fixture.receipt.receipt_id);
  await page.locator('[name="assignment_id"]').selectOption(fixture.assignment.assignment_id);
}
async function openHuman(page, fixture) {
  await selectHuman(page, fixture);
  await page.getByRole('button', {name: 'Open selected assigned case', exact: true}).click();
  await expect(page.locator('#next-action')).toBeEnabled();
  await expect(page.locator('#physician-code')).toHaveValue(fixture.code);
}
async function downloadJSON(page, action) {
  const downloading = page.waitForEvent('download');
  await action();
  const download = await downloading;
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
function digest(value) { return createHash('sha256').update(canonical(value)).digest('hex'); }
function barrier() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, release: () => resolve()};
}
module.exports = {test, expect, get, post, governanceBody, planBody, recordReview, setupHuman, recordPermission,
  ready, openQA, values, fillResponse, saveResponse, selectHuman, openHuman, downloadJSON, digest, barrier};
