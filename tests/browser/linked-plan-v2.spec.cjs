const {randomUUID} = require('node:crypto');
const {test, expect, get, post, planBody, recordReview, ready, selectHuman, openHuman,
  values, fillResponse, saveResponse, downloadJSON} = require('./helpers.cjs');
const {approveV2} = require('./contracts.cjs');

function rulesForm(page) {
  return page.locator('#collection-view article').filter({has: page.getByRole('heading', {name: 'Save collection rules', exact: true})});
}
function assignmentForm(page) {
  return page.locator('#collection-view article').filter({has: page.getByRole('heading', {name: 'Plan a demo assignment', exact: true})});
}
async function savePlan(page) {
  const saved = page.waitForResponse(response => response.url().endsWith('/api/protocols') && response.request().method() === 'POST');
  await page.getByRole('button', {name: 'Save protocol revision', exact: true}).click();
  const response = await saved;
  expect(response.status(), await response.text()).toBe(201);
  const result = (await response.json()).protocol;
  await expect(rulesForm(page).locator('[name="title"]')).toHaveValue(result.title);
  await expect(assignmentForm(page).locator('[name="protocol_id"]')).toHaveValue(result.protocol_id);
  return result;
}
async function assign(page, code, version, status = 201) {
  const form = assignmentForm(page);
  await form.getByLabel('Allowed physician code', {exact: true}).selectOption(code);
  await form.getByLabel('Exact case version', {exact: true}).selectOption(version.version_id);
  const saved = page.waitForResponse(response => response.url().endsWith('/api/assignments') && response.request().method() === 'POST');
  await form.getByRole('button', {name: 'Save demo assignment', exact: true}).click();
  const response = await saved;
  expect(response.status(), await response.text()).toBe(status);
  const body = await response.json();
  if (status === 201) await expect(assignmentForm(page).locator('[name="version_id"]')).toHaveValue('');
  else await expect(form.locator('.save-status')).toContainText('Save conflict');
  return body.assignment;
}
async function agreeViaUI(page, code) {
  await page.getByRole('button', {name: 'Capture', exact: true}).click();
  await expect(page.locator('#capture-mode')).toHaveAttribute('aria-busy', 'false');
  await page.locator('[name="capture_mode"]').selectOption('physician_demo');
  await expect(page.locator('[name="choice"]')).toHaveValue('');
  await page.locator('#capture-mode [name="physician_code"]').fill(code);
  await page.locator('[name="choice"]').selectOption('agree');
  const receipt = await downloadJSON(page, () => page.getByRole('button', {name: 'Record permission choice', exact: true}).click());
  await expect(page.locator(`[name="permission_receipt_id"] option[value="${receipt.receipt_id}"]`)).toHaveCount(1);
  return receipt;
}

test('deliberate legacy-to-linked plan cutover preserves history, scope limits and current permission', async ({page, request, browserChecks}) => {
  const code = `LINKED-${randomUUID().slice(0, 8)}`;
  const before = await get(request, '/api/collection');
  expect(before.current?.protocol_schema_version || '1.0').toBe('1.0');
  const legacyBody = planBody(before.current?.protocol_id || null, code);
  legacyBody.consent_statement = 'Historical fabricated planning text; never current permission.';
  legacyBody.retention_days = 11;
  const legacy = (await post(request, '/api/protocols', legacyBody)).protocol;
  const {governance} = await approveV2(request, {limit: 2});
  await post(request, '/api/permissions', {request_id: randomUUID(), governance_id: governance.governance_id,
    physician_code: code, choice: 'agree'}, 409);
  const versions = (await get(request, '/api/catalog')).versions.slice(-3);
  for (const version of versions) await recordReview(request, version);
  await ready(page);
  await page.getByRole('button', {name: 'Collection plan', exact: true}).click();
  let form = rulesForm(page);
  await form.locator('[name="governance_id"]').selectOption(governance.governance_id);
  await form.getByLabel('Plan title', {exact: true}).fill('Fabricated linked scope one');
  await form.getByLabel('Allowed physician codes', {exact: true}).fill(code);
  await form.getByLabel('Collection owner code', {exact: true}).fill('STF-BROWSER');
  await form.getByLabel('Backup owner code', {exact: true}).fill('STF-BROWSER');
  await expect(form).toContainText(governance.permission.text.trim());
  await expect(form).toContainText(governance.session.description);
  for (const name of ['consent_statement', 'consent_version', 'retention_days', 'backup_retention_days']) {
    await expect(form.locator(`[name="${name}"]`)).toHaveCount(0);
  }
  const linked = await savePlan(page);
  expect(linked.protocol_schema_version).toBe('2.0');
  expect(linked.governance_id).toBe(governance.governance_id);
  for (const name of ['consent_statement', 'consent_version', 'retention_days', 'backup_retention_days']) expect(linked).not.toHaveProperty(name);
  expect((await get(request, '/api/collection')).history.find(item => item.protocol_id === legacy.protocol_id)).toEqual(legacy);
  const retry = await post(request, '/api/protocols', legacyBody, 200);
  expect(retry).toEqual({protocol: legacy, duplicate: true});
  expect((await get(request, '/api/collection')).current).toEqual(linked);
  await post(request, '/api/protocols', planBody(linked.protocol_id, code), 409);
  expect((await get(request, '/api/collection')).current).toEqual(linked);

  await assign(page, code, versions[0]);
  await assign(page, code, versions[1]);
  form = rulesForm(page);
  await form.getByLabel('Plan title', {exact: true}).fill('Fabricated linked scope one revision');
  const revision = await savePlan(page);
  expect(revision.governance_id).toBe(governance.governance_id);
  browserChecks.allowError('/api/assignments', /409 \(Conflict\)/);
  await assign(page, code, versions[2], 409);
  let collection = await get(request, '/api/collection');
  expect(collection.assignments.filter(item => item.physician_code === code)).toHaveLength(2);
  page.once('dialog', dialog => dialog.accept());
  await assignmentForm(page).getByRole('button', {name: 'Discard this draft and refresh', exact: true}).click();
  await expect(assignmentForm(page).locator('[name="version_id"]')).toHaveValue('');
  const repeatedAssignment = await assign(page, code, versions[0]);
  const receipt = await agreeViaUI(page, code);
  expect(receipt.session).toEqual(governance.session);
  expect(receipt.professional_role).toBe(governance.operator.professional_role);
  expect(receipt.pilot_window).toEqual({pilot_start_date: governance.operator.pilot_start_date, pilot_close_date: governance.operator.pilot_close_date});
  await expect(page.locator('#capture-mode')).toContainText(governance.session.description);
  await expect(page.locator('#capture-mode')).toContainText('no total-response or time limit');
  await openHuman(page, {code, receipt, assignment: repeatedAssignment});
  await fillResponse(page, values(code));
  const original = await saveResponse(page);
  expect(original.governance_id).toBe(governance.governance_id);
  await page.locator('#new-response').click();
  await expect(page.locator('#next-action')).toBeEnabled();
  await fillResponse(page, values(code));
  await saveResponse(page);
  await page.getByRole('button', {name: 'Review responses', exact: true}).click();
  const card = page.locator('.review-card').filter({hasText: original.response_id});
  await card.getByRole('button', {name: 'Create correction', exact: true}).click();
  await expect(page.locator('#correction-notice')).toContainText(original.response_id);
  await page.locator('#next-action').fill('Fabricated linked correction.');
  const correction = await saveResponse(page);
  expect(correction.supersedes_response_id).toBe(original.response_id);
  expect(correction.permission_receipt_id).toBe(receipt.receipt_id);
  collection = await get(request, '/api/collection');
  const scopeAssignments = collection.assignments.filter(item => item.physician_code === code);
  expect(new Set(scopeAssignments.map(item => item.version_id)).size).toBe(2);
  const exported = await get(request, '/api/export');
  const serialized = JSON.stringify(exported);
  for (const privateText of [governance.session.description, governance.operator.professional_role, governance.permission.text]) {
    expect(serialized).not.toContain(JSON.stringify(privateText).slice(1, -1));
  }
  expect(exported.responses.filter(item => item.physician_code === code)).toHaveLength(3);
  await ready(page); // The correction is saved; a fresh view starts the next scope workflow.
  await selectHuman(page, {receipt, assignment: repeatedAssignment});

  const {governance: nextGovernance} = await approveV2(request, {limit: 2, description: 'Fabricated explicitly revised case-set scope.'});
  await page.getByRole('button', {name: 'Capture', exact: true}).click();
  await expect(page.locator('#capture-mode')).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('[name="assignment_id"]')).toHaveCount(0);
  await expect(page.locator('[name="permission_receipt_id"]')).toHaveCount(0);
  await expect(page.locator('[name="capture_mode"] option[value="physician_demo"]')).toBeDisabled();
  await expect(page.locator('#capture-mode > [role="status"]')).toContainText('no longer available');
  await expect(page.locator('#capture-mode > [role="status"]')).toContainText('save a revised plan explicitly');
  await page.getByRole('button', {name: 'Collection plan', exact: true}).click();
  await expect(page.locator('#collection-view')).toContainText(/stale|earlier governance|governance changed/i);
  expect((await get(request, '/api/collection')).current.governance_id).toBe(governance.governance_id);
  await post(request, '/api/permissions', {request_id: randomUUID(), governance_id: nextGovernance.governance_id,
    physician_code: code, choice: 'agree'}, 409);
  form = rulesForm(page);
  await expect(form).toContainText(governance.session.description);
  await form.locator('[name="governance_id"]').selectOption(nextGovernance.governance_id);
  await expect(form).toContainText(nextGovernance.session.description);
  await expect(form).not.toContainText(governance.session.description);
  await form.getByLabel('Plan title', {exact: true}).fill('Fabricated explicitly revised scope plan');
  const nextPlan = await savePlan(page);
  expect(nextPlan.governance_id).toBe(nextGovernance.governance_id);
  await expect(rulesForm(page)).toContainText(nextGovernance.session.description);
  const newAssignment = await assign(page, code, versions[2]);
  const nextReceipt = await agreeViaUI(page, code);
  expect(nextReceipt.governance_id).toBe(nextGovernance.governance_id);
  expect(nextReceipt.receipt_id).not.toBe(receipt.receipt_id);
  await expect(page.locator(`[name="permission_receipt_id"] option[value="${receipt.receipt_id}"]`)).toHaveCount(0);
  await openHuman(page, {code, receipt: nextReceipt, assignment: newAssignment});
  await expect(page.locator('#next-action')).toBeEnabled();
  expect((await get(request, '/api/governance')).receipts.find(item => item.receipt_id === receipt.receipt_id)).toEqual(receipt);
});
