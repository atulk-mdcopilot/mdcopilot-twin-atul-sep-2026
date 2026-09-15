const {randomUUID, createHash} = require('node:crypto');
const {test, expect, get, post, setupHuman, recordPermission, recordReview, governanceBody, planBody,
  ready, openHuman, values, fillResponse, downloadJSON} = require('./helpers.cjs');

test('permission starts unselected; Agree downloads exact notice, Decline cannot open a response', async ({page, request}) => {
  const fixture = await setupHuman(request, {permission: false});
  await ready(page);
  await page.locator('[name="capture_mode"]').selectOption('physician_demo');
  await expect(page.locator('[name="choice"]')).toHaveValue('');
  await expect(page.locator('.exact-notice')).toHaveText(fixture.governance.permission.text);
  await page.locator('#capture-mode [name="physician_code"]').fill(fixture.code);
  await page.locator('[name="choice"]').selectOption('agree');
  const agreed = await downloadJSON(page, () => page.getByRole('button', {name: 'Record permission choice', exact: true}).click());
  expect(agreed.choice).toBe('agree');
  expect(agreed.physician_code).toBe(fixture.code);
  expect(agreed.permission_text).toBe(fixture.governance.permission.text);
  expect(agreed.permission_sha256).toBe(createHash('sha256').update(agreed.permission_text).digest('hex'));
  await expect(page.locator('[name="choice"]')).toHaveValue('');
  await expect(page.locator('[name="permission_receipt_id"] option')).toHaveCount(2);
  await page.locator('#capture-mode [name="physician_code"]').fill(fixture.code);
  await page.locator('[name="choice"]').selectOption('decline');
  const declined = await downloadJSON(page, () => page.getByRole('button', {name: 'Record permission choice', exact: true}).click());
  expect(declined.choice).toBe('decline');
  await expect(page.locator('#capture-mode > [role="status"]')).toContainText('Decline recorded');
  await expect(page.locator('[name="permission_receipt_id"] option')).toHaveCount(1);
  await page.getByRole('button', {name: 'Open selected assigned case', exact: true}).click();
  await expect(page.locator('#presentation-status')).toContainText('Agree receipt');
  expect((await get(request, '/api/responses')).responses.filter(item => item.physician_code === fixture.code)).toEqual([]);
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
});

test('permission draft survives tab navigation and prevents silent mode changes', async ({page, request}) => {
  const fixture = await setupHuman(request, {permission: false});
  await ready(page);
  await page.locator('[name="capture_mode"]').selectOption('physician_demo');
  await page.locator('#capture-mode [name="physician_code"]').fill(fixture.code);
  await page.locator('[name="choice"]').selectOption('agree');
  await page.getByRole('button', {name: 'Case lab', exact: true}).click();
  await page.getByRole('button', {name: 'Capture', exact: true}).click();
  await expect(page.locator('#capture-mode [name="physician_code"]')).toHaveValue(fixture.code);
  await expect(page.locator('[name="choice"]')).toHaveValue('agree');
  await page.locator('[name="capture_mode"]').selectOption('fabricated_qa');
  await expect(page.locator('[name="capture_mode"]')).toHaveValue('physician_demo');
  await expect(page.locator('#capture-mode > [role="status"]')).toContainText('Finish or discard');
  expect((await get(request, '/api/governance')).receipts.filter(item => item.physician_code === fixture.code)).toEqual([]);
});

for (const change of ['decline', 'governance', 'review', 'plan', 'code']) {
  test(`real server rejects a presented human response after ${change} changes`, async ({page, request, browserChecks}) => {
    const fixture = await setupHuman(request);
    await ready(page);
    await openHuman(page, fixture);
    const answer = values(fixture.code);
    await fillResponse(page, answer);
    if (change === 'decline') await recordPermission(request, fixture.governance, fixture.code, 'decline');
    if (change === 'governance') await post(request, '/api/governance', governanceBody(fixture.governance.governance_id));
    if (change === 'review') await recordReview(request, fixture.version, 'needs_revision');
    if (change === 'plan') await post(request, '/api/protocols', planBody(fixture.protocol.protocol_id, fixture.code));
    if (change === 'code') {
      await page.route('**/api/responses', route => {
        const body = route.request().postDataJSON();
        body.values.physician_code = `${fixture.code}-OTHER`;
        return route.continue({postData: JSON.stringify(body)});
      }, {times: 1});
    }
    browserChecks.allowError('/api/responses', /409 \(Conflict\)/);
    await page.locator('#save-response').click();
    await expect(page.locator('#save-status')).toContainText('Save conflict');
    await expect(page.locator('#next-action')).toBeDisabled();
    await expect(page.locator('#next-action')).toHaveValue(answer.next_action);
    expect((await get(request, '/api/responses')).responses.filter(item => item.physician_code === fixture.code)).toEqual([]);
  });
}

test('a receipt never authorizes another physician assignment', async ({page, request, browserChecks}) => {
  const fixture = await setupHuman(request);
  const other = (await post(request, '/api/assignments', {request_id: randomUUID(), protocol_id: fixture.protocol.protocol_id,
    physician_code: `${fixture.code}-OTHER`, version_id: fixture.version.version_id, notes: 'Fabricated other-code assignment.'})).assignment;
  await ready(page);
  await page.locator('[name="capture_mode"]').selectOption('physician_demo');
  await page.locator('[name="permission_receipt_id"]').selectOption(fixture.receipt.receipt_id);
  await expect(page.locator(`[name="assignment_id"] option[value="${other.assignment_id}"]`)).toHaveCount(0);
  await page.locator('[name="assignment_id"]').selectOption(fixture.assignment.assignment_id);
  browserChecks.allowError('/api/presentations', /409 \(Conflict\)/);
  await page.route('**/api/presentations', route => {
    const body = route.request().postDataJSON();
    return route.continue({postData: JSON.stringify({...body, assignment_id: other.assignment_id})});
  }, {times: 1});
  await page.getByRole('button', {name: 'Open selected assigned case', exact: true}).click();
  await expect(page.locator('#presentation-status')).toContainText('Could not open');
  await expect(page.locator('#next-action')).toBeDisabled();
});
