// Versioned fixtures contain fabricated identities, notices and attestations only.
const {governanceBody, get, post, expect} = require('./helpers.cjs');

function governanceV2(parent = null, status = 'approved') {
  const body = governanceBody(parent, status);
  body.governance_schema_version = '2.0';
  body.operator.professional_role = 'Fabricated gastroenterology test role';
  body.operator.pilot_start_date = new Date().toISOString().slice(0, 10);
  body.session = {
    description: 'Fabricated assigned case set. Repeated attempts and corrections remain separate observations.',
    max_distinct_case_versions: 2,
  };
  const close = new Date(`${body.operator.pilot_close_date}T00:00:00Z`);
  const anniversary = new Date(close);
  // The fixture explicitly chooses March 1 if its generated close is February 29.
  anniversary.setUTCFullYear(anniversary.getUTCFullYear() + 1);
  const days = (anniversary - close) / 86400000;
  body.retention.calendar_year_basis = {pilot_close_date: body.operator.pilot_close_date,
    anniversary_date: anniversary.toISOString().slice(0, 10)};
  body.retention.permission_after_close_days = days;
  body.retention.audit_after_close_days = days;
  return body;
}
async function approveV2(request, {limit = 2, description} = {}) {
  const {current} = await get(request, '/api/governance');
  const body = governanceV2(current?.governance_id || null);
  body.session.max_distinct_case_versions = limit;
  if (description) body.session.description = description;
  return {body, governance: (await post(request, '/api/governance', body)).governance};
}
function operatingForm(page) {
  return page.locator('#governance-view article').filter({has: page.getByRole('heading', {name: 'Local operating record', exact: true})});
}
async function showDetails(form, summary) {
  const toggle = form.getByText(summary, {exact: true});
  const details = toggle.locator('..');
  if ((await details.getAttribute('open')) === null) await toggle.click();
}
async function saveOperating(page, expected = 201) {
  const saving = page.waitForResponse(response => response.url().endsWith('/api/governance') && response.request().method() === 'POST');
  await page.getByRole('button', {name: 'Save operating record', exact: true}).click();
  const result = await saving;
  const body = await result.json();
  expect(result.status(), JSON.stringify(body)).toBe(expected);
  if (body.governance) await expect(page.locator('#governance-view')).toContainText(body.governance.governance_id);
  return body.governance;
}
module.exports = {governanceV2, approveV2, operatingForm, showDetails, saveOperating};
