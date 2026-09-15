const {test, expect, get, post, ready} = require('./helpers.cjs');
const {governanceV2, operatingForm, showDetails, saveOperating} = require('./contracts.cjs');

async function openOperating(page) {
  await ready(page);
  await page.getByRole('button', {name: 'Governance', exact: true}).click();
  const form = operatingForm(page);
  await expect(form.getByRole('heading', {name: 'Local operating record', exact: true})).toBeVisible();
  await showDetails(form, 'Operator and pilot dates');
  await showDetails(form, 'Participant session and assigned case set');
  return form;
}
async function seedDraft(request) {
  const {current} = await get(request, '/api/governance');
  return (await post(request, '/api/governance', governanceV2(current?.governance_id || null, 'draft'))).governance;
}

test('legacy records keep missing pilot facts unknown; explicit draft saves structured fields', async ({page, request}) => {
  const before = (await get(request, '/api/governance')).current;
  expect(before.governance_schema_version).toBe('1.0');
  const form = await openOperating(page);
  for (const name of ['operator.professional_role', 'operator.pilot_start_date', 'session.description', 'session.max_distinct_case_versions']) {
    await expect(form.locator(`[name="${name}"]`)).toHaveValue('');
  }
  await expect(form.locator('[name="status"]')).toHaveValue('draft');
  await form.getByLabel('Policy title', {exact: true}).fill('Fabricated structured pilot draft');
  await form.getByLabel('Professional role', {exact: true}).fill('Fabricated test reviewer role');
  await form.getByLabel('Pilot start date (UTC)', {exact: true}).fill('2027-02-20');
  await form.getByLabel('Planned pilot close date (UTC)', {exact: true}).fill('2027-02-28');
  await form.getByLabel('Participant-facing session description', {exact: true}).fill('Fabricated assigned-case set; no total-attempt cap.');
  await form.getByLabel('Maximum distinct case versions per physician', {exact: true}).fill('2');
  await showDetails(form, 'Retention decisions — approved policy values');
  await expect(form.locator('[name="retention.permission_after_close_days"]')).toHaveValue('');
  await expect(form.locator('[name="retention.audit_after_close_days"]')).toHaveValue('');
  await form.getByRole('button', {name: 'Calculate calendar-year periods', exact: true}).click();
  const saved = await saveOperating(page);
  expect(saved.governance_schema_version).toBe('2.0');
  expect(saved.operator.professional_role).toBe('Fabricated test reviewer role');
  expect(saved.operator.pilot_start_date).toBe('2027-02-20');
  expect(saved.session).toEqual({description: 'Fabricated assigned-case set; no total-attempt cap.', max_distinct_case_versions: 2});
  expect(saved.retention.calendar_year_basis).toEqual({pilot_close_date: '2027-02-28', anniversary_date: '2028-02-28'});
  expect(saved.status).toBe('draft');
  const after = await get(request, '/api/governance');
  expect(after.history.find(item => item.governance_id === before.governance_id)).toEqual(before);
  expect(after.readiness.actual_physician_capture_enabled).toBe(false);
  expect(saved.controls.device_encryption_verified).toBe(false);
  expect(saved.approved_by_code).toBe('');
});

test('invalid date order and invalid assigned-case limits cannot save; correcting values is recoverable', async ({page, request, browserChecks}) => {
  const original = await seedDraft(request);
  const form = await openOperating(page);
  await form.getByLabel('Pilot start date (UTC)', {exact: true}).fill('2028-03-02');
  await form.getByLabel('Planned pilot close date (UTC)', {exact: true}).fill('2028-03-01');
  browserChecks.allowError('/api/governance', /400 \(Bad Request\)/);
  await saveOperating(page, 400);
  await expect(form.locator('.save-status')).toContainText('Update the fields');
  expect((await get(request, '/api/governance')).current).toEqual(original);
  await form.getByLabel('Pilot start date (UTC)', {exact: true}).fill('2028-02-20');
  const limit = form.getByLabel('Maximum distinct case versions per physician', {exact: true});
  for (const invalid of ['0', '201', '1.5']) {
    await limit.fill(invalid);
    await form.getByRole('button', {name: 'Save operating record', exact: true}).click();
    expect(await limit.evaluate(input => input.validity.valid)).toBe(false);
    expect((await get(request, '/api/governance')).current.governance_id).toBe(original.governance_id);
  }
  await limit.fill('3');
  const saved = await saveOperating(page);
  expect(saved.session.max_distinct_case_versions).toBe(3);
  expect(saved.retention.calendar_year_basis).toBeNull();
  expect(saved.retention.permission_after_close_days).toBeNull();
  expect(saved.retention.audit_after_close_days).toBeNull();
});

test('calendar conversion requires a leap-day choice and changing closure clears its saved draft basis', async ({page, request}) => {
  await seedDraft(request);
  let form = await openOperating(page);
  await form.getByLabel('Pilot start date (UTC)', {exact: true}).fill('2028-02-01');
  await form.getByLabel('Planned pilot close date (UTC)', {exact: true}).fill('2028-02-29');
  await showDetails(form, 'Retention decisions — approved policy values');
  await form.getByRole('button', {name: 'Calculate calendar-year periods', exact: true}).click();
  await expect(form).toContainText('requires an explicit February 28 or March 1');
  await expect(form.locator('[name="retention.permission_after_close_days"]')).toHaveValue('');
  await form.getByLabel('Anniversary convention for a February 29 close date', {exact: true}).selectOption('feb28');
  await form.getByRole('button', {name: 'Calculate calendar-year periods', exact: true}).click();
  await expect(form.locator('[name="retention.permission_after_close_days"]')).toHaveValue('365');
  const first = await saveOperating(page);
  expect(first.retention.calendar_year_basis).toEqual({pilot_close_date: '2028-02-29', anniversary_date: '2029-02-28'});
  form = operatingForm(page);
  await showDetails(form, 'Retention decisions — approved policy values');
  await form.getByLabel('Anniversary convention for a February 29 close date', {exact: true}).selectOption('mar1');
  await expect(form.locator('[name="retention.permission_after_close_days"]')).toHaveValue('');
  await expect(form.locator('[name="retention.audit_after_close_days"]')).toHaveValue('');
  await form.getByRole('button', {name: 'Calculate calendar-year periods', exact: true}).click();
  await expect(form.locator('[name="retention.permission_after_close_days"]')).toHaveValue('366');
  await expect(form.locator('[name="retention.audit_after_close_days"]')).toHaveValue('366');
  const second = await saveOperating(page);
  expect(second.retention.calendar_year_basis).toEqual({pilot_close_date: '2028-02-29', anniversary_date: '2029-03-01'});
  form = operatingForm(page);
  await showDetails(form, 'Operator and pilot dates');
  await form.getByLabel('Planned pilot close date (UTC)', {exact: true}).fill('2028-03-01');
  await showDetails(form, 'Retention decisions — approved policy values');
  await expect(form.locator('[name="retention.permission_after_close_days"]')).toHaveValue('');
  await expect(form.locator('[name="retention.audit_after_close_days"]')).toHaveValue('');
  const third = await saveOperating(page);
  expect(third.retention.calendar_year_basis).toBeNull();
  expect(third.retention.permission_after_close_days).toBeNull();
  expect((await get(request, '/api/governance')).history.find(item => item.governance_id === first.governance_id)).toEqual(first);
});
