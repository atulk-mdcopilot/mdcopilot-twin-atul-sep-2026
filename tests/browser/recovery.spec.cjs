const {test, expect, get, ready, openQA, values, fillResponse, saveResponse} = require('./helpers.cjs');

for (const committed of [false, true]) {
  test(`${committed ? 'committed save with lost reply' : 'request lost before commit'} retries unchanged exactly once`, async ({page, request, browserChecks}) => {
    await ready(page);
    const presentation = await openQA(page);
    const answer = values();
    await fillResponse(page, answer);
    browserChecks.allowError('/api/responses', /net::ERR_FAILED/);
    let originalRequest;
    await page.route('**/api/responses', async route => {
      if (route.request().method() !== 'POST') return route.continue();
      originalRequest = route.request().postDataJSON();
      if (committed) {
        const response = await route.fetch();
        expect(response.status()).toBe(201);
      }
      await route.abort('failed');
    }, {times: 1});
    await page.locator('#save-response').click();
    await expect(page.locator('#save-status')).toContainText('Save not confirmed');
    await expect(page.locator('#next-action')).toBeDisabled();
    const saved = (await get(request, '/api/responses')).responses.filter(item => item.presentation_id === presentation.presentation_id);
    expect(saved).toHaveLength(committed ? 1 : 0);
    await page.getByRole('button', {name: 'Review responses', exact: true}).click();
    await page.getByRole('button', {name: 'Capture', exact: true}).click();
    await expect(page.locator('#next-action')).toHaveValue(answer.next_action);
    await expect(page.locator('#next-action')).toBeDisabled();
    const retried = page.waitForResponse(response => response.url().endsWith('/api/responses') && response.request().method() === 'POST');
    await page.getByRole('button', {name: 'Retry unchanged save', exact: true}).click();
    const response = await retried;
    expect(response.status()).toBe(committed ? 200 : 201);
    expect(response.request().postDataJSON()).toEqual(originalRequest);
    await expect(page.locator('#save-status')).toContainText(committed ? 'Existing save confirmed' : 'Saved locally');
    const rows = (await get(request, '/api/responses')).responses.filter(item => item.presentation_id === presentation.presentation_id);
    expect(rows).toHaveLength(1);
    expect(rows[0].original_values).toEqual(answer);
    if (committed) expect(rows[0]).toEqual(saved[0]);
  });
}

test('server validation is editable; conflict preserves pending values across navigation', async ({page, request, browserChecks}) => {
  await ready(page);
  const presentation = await openQA(page);
  const answer = values();
  await fillResponse(page, answer);
  browserChecks.allowError('/api/responses', /400 \(Bad Request\)/);
  browserChecks.allowError('/api/responses', /409 \(Conflict\)/);
  // Only the field boundary is changed: the real server validates and rejects it.
  await page.route('**/api/responses', route => {
    const body = route.request().postDataJSON();
    body.values.confidence = 'INVALID-TEST-CHOICE';
    return route.continue({postData: JSON.stringify(body)});
  }, {times: 1});
  await page.locator('#save-response').click();
  await expect(page.locator('#save-status')).toContainText('Update the fields');
  await expect(page.locator('#next-action')).toBeEnabled();
  const corrected = {...answer, next_action: 'Fabricated editable corrected answer.'};
  await page.locator('#next-action').fill(corrected.next_action);
  const saved = await saveResponse(page);
  expect(saved.original_values).toEqual(corrected);
  // A real concurrent save with different values makes this open presentation conflict.
  await page.locator('[name="qa_acknowledged"]').check();
  await page.locator('#new-response').click();
  await expect(page.locator('#next-action')).toBeEnabled();
  await fillResponse(page, answer);
  await page.route('**/api/responses', async route => {
    const body = route.request().postDataJSON();
    const concurrent = await request.post('http://127.0.0.1:8765/api/responses', {
      headers: {'X-Twin-Lab': '1'}, data: {...body, values: {...body.values, next_action: 'Concurrent fabricated answer.'}},
    });
    expect(concurrent.status()).toBe(201);
    await route.continue();
  }, {times: 1});
  await page.locator('#save-response').click();
  await expect(page.locator('#save-status')).toContainText('Save conflict');
  await expect(page.locator('#next-action')).toBeDisabled();
  await page.getByRole('button', {name: 'Review responses', exact: true}).click();
  await page.getByRole('button', {name: 'Capture', exact: true}).click();
  await expect(page.locator('#next-action')).toHaveValue(answer.next_action);
  await expect(page.locator('#next-action')).toBeDisabled();
  await expect(page.locator('#save-response')).toHaveText('Retry unchanged save');
  expect((await get(request, '/api/responses')).responses.filter(item => item.presentation_id === presentation.presentation_id)).toHaveLength(1);
});
