const {test, expect, get, ready, openQA, values, fillResponse, saveResponse, downloadJSON, digest} = require('./helpers.cjs');

test('all tabs load real modules, retain the prototype notice and support keyboard theme choice', async ({page}) => {
  await ready(page);
  for (const name of ['Review responses', 'Case lab', 'Collection plan', 'Governance', 'Capture']) {
    const tab = page.getByRole('button', {name, exact: true});
    await tab.focus();
    await page.keyboard.press('Enter');
    await expect(tab).toBeFocused();
    await expect(tab).toHaveAttribute('aria-current', 'page');
    await expect(page.getByRole('complementary', {name: 'Prototype limitations'})).toBeVisible();
    await expect(page.locator('.prototype-notice')).toContainText('Not a validated clinical tool');
  }
  const theme = page.getByRole('button', {name: 'Dark mode', exact: true});
  await theme.focus();
  await page.keyboard.press('Space');
  await expect(theme).toBeFocused();
  await expect(theme).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(await page.evaluate(() => Object.entries(localStorage))).toEqual([['twin-lab-theme', 'dark']]);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', {name: 'Skip to content'})).toBeFocused();
});

test('QA acknowledgement and required values are enforced and acknowledgement resets for each presentation', async ({page, request}) => {
  await ready(page);
  const before = (await get(request, '/api/responses')).responses.length;
  await page.locator('#case-list button').first().click();
  await expect(page.locator('#presentation-status')).toContainText('Acknowledge');
  await expect(page.locator('#next-action')).toBeDisabled();
  await openQA(page);
  await expect(page.locator('[name="qa_acknowledged"]')).not.toBeChecked();
  await page.locator('#save-response').click();
  await expect(page.locator('#physician-code')).toBeFocused();
  const answer = values();
  await fillResponse(page, {...answer, next_action: '   '});
  await page.locator('#save-response').click();
  expect(await page.locator('#next-action').evaluate(input => input.validationMessage)).toContain('spaces alone');
  expect((await get(request, '/api/responses')).responses).toHaveLength(before);
  await page.locator('#next-action').fill(answer.next_action);
  await saveResponse(page);
  await page.locator('#new-response').click();
  await expect(page.locator('#presentation-status')).toContainText('Acknowledge');
  await page.locator('[name="qa_acknowledged"]').check();
  await page.locator('#retry-presentation').click();
  await expect(page.locator('#next-action')).toBeEnabled();
  await expect(page.locator('[name="qa_acknowledged"]')).not.toBeChecked();
});

test('save, reload, review, correction and JSON download preserve exact values and snapshots', async ({page, request}) => {
  await ready(page);
  const presentation = await openQA(page);
  const answer = values();
  answer.physician_code = `  ${answer.physician_code}  `;
  await fillResponse(page, answer);
  const original = await saveResponse(page);
  expect(original.original_values).toEqual(answer);
  expect(original.case_snapshot).toEqual(presentation.case_snapshot);
  expect(original.snapshot_sha256).toBe(digest(presentation.case_snapshot));
  expect(original.physician_code).toBe(answer.physician_code.trim());
  expect(original.supersedes_response_id).toBeNull();
  await page.reload();
  await page.getByRole('button', {name: 'Review responses', exact: true}).click();
  let card = page.locator('.review-card').filter({hasText: original.response_id});
  await expect(card).toContainText(answer.next_action.trim());
  await expect(card.locator('em')).toHaveCount(0);
  await card.getByText('Exact presented case', {exact: true}).click();
  await expect(card.locator('.review-snapshot')).toContainText(presentation.case_snapshot.title);
  await page.getByRole('button', {name: 'Capture', exact: true}).click();
  await page.locator('[name="qa_acknowledged"]').check();
  await page.getByRole('button', {name: 'Review responses', exact: true}).click();
  await card.getByRole('button', {name: 'Create correction'}).click();
  await expect(page.locator('#correction-notice')).toContainText(original.response_id);
  await expect(page.locator('#physician-code')).toHaveAttribute('readonly', '');
  const correctedValues = {...answer, next_action: '  Fabricated appended correction.  '};
  await page.locator('#next-action').fill(correctedValues.next_action);
  await page.getByRole('button', {name: 'Review responses', exact: true}).click();
  await page.getByRole('button', {name: 'Capture', exact: true}).click();
  await expect(page.locator('#next-action')).toHaveValue(correctedValues.next_action);
  await expect(page.locator('#correction-notice')).toContainText(original.response_id);
  const correction = await saveResponse(page);
  expect(correction.supersedes_response_id).toBe(original.response_id);
  expect(correction.original_values).toEqual(correctedValues);
  for (const key of ['case_snapshot', 'snapshot_sha256', 'case_version_id', 'physician_code']) {
    expect(correction[key]).toEqual(original[key]);
  }
  await page.getByRole('button', {name: 'Review responses', exact: true}).click();
  await page.getByRole('button', {name: 'Refresh', exact: true}).click();
  card = page.locator('.review-card').filter({hasText: original.response_id}).filter({has: page.locator(".subtle-tag").filter({hasText: /^Original$/})});
  await expect(card).toContainText('original remains preserved');
  const exported = await downloadJSON(page, () => page.locator('#export-responses').click());
  expect(exported.responses.filter(item => item.physician_code === answer.physician_code.trim())).toEqual([original, correction]);
  expect((await get(request, '/api/responses')).responses.find(item => item.response_id === original.response_id)).toEqual(original);
});
