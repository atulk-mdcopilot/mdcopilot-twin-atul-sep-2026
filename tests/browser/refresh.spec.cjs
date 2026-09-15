const {test, expect, post, setupHuman, recordPermission, recordReview, governanceBody,
  ready, selectHuman, barrier} = require('./helpers.cjs');

test('valid receipt and assignment survive navigation without requiring re-selection', async ({page, request}) => {
  const fixture = await setupHuman(request);
  await ready(page);
  await selectHuman(page, fixture);
  await page.getByRole('button', {name: 'Review responses', exact: true}).click();
  const refreshed = page.waitForResponse(response => response.url().endsWith('/api/governance'));
  await page.getByRole('button', {name: 'Capture', exact: true}).click();
  await refreshed;
  await expect(page.locator('#capture-mode')).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('[name="permission_receipt_id"]')).toHaveValue(fixture.receipt.receipt_id);
  await expect(page.locator('[name="assignment_id"]')).toHaveValue(fixture.assignment.assignment_id);
});

for (const invalidation of ['declined receipt', 'unapproved assignment']) {
  test(`refresh clears and explains an invalid ${invalidation}`, async ({page, request}) => {
    const fixture = await setupHuman(request);
    await ready(page);
    await selectHuman(page, fixture);
    if (invalidation === 'declined receipt') await recordPermission(request, fixture.governance, fixture.code, 'decline');
    else await recordReview(request, fixture.version, 'rejected');
    await page.getByRole('button', {name: 'Capture', exact: true}).click();
    await expect(page.locator('[name="assignment_id"]')).toHaveValue('');
    if (invalidation === 'declined receipt') await expect(page.locator('[name="permission_receipt_id"]')).toHaveValue('');
    else await expect(page.locator('[name="permission_receipt_id"]')).toHaveValue(fixture.receipt.receipt_id);
    await expect(page.locator('#capture-mode > [role="status"]')).toContainText(/no longer|changed|invalid|unavailable/i);
  });
}

// Use the public module API in an extra test-only DOM container so refresh completion
// is directly awaitable. The real module, fetch transport and server are unchanged.
async function refreshHarness(page) {
  await page.evaluate(async () => {
    const {initCaptureMode} = await import('/capture-mode.js');
    const container = document.createElement('section');
    container.id = 'refresh-regression';
    document.body.append(container);
    window.refreshRegression = initCaptureMode(container, {onOpenAssignment() {}, onModeChange: () => true});
    await window.refreshRegression.refresh();
  });
}

for (const olderFailure of [false, true]) {
  test(`late older ${olderFailure ? 'failure' : 'success'} cannot replace a newer refresh`, async ({page, request, browserChecks}) => {
    const fixture = await setupHuman(request);
    await ready(page);
    await refreshHarness(page);
    const arrived = barrier();
    const release = barrier();
    let held = false;
    await page.route('**/api/governance', async route => {
      if (held) return route.continue();
      held = true;
      const response = await route.fetch();
      expect(response.status()).toBe(200);
      arrived.release();
      await release.promise;
      if (olderFailure) await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({error: 'Fabricated older reply failure'})});
      else await route.fulfill({response});
    });
    if (olderFailure) browserChecks.allowError('/api/governance', /503 \(Service Unavailable\)/);
    const older = page.evaluate(() => window.refreshRegression.refresh());
    try {
      await arrived.promise;
      if (!olderFailure) await post(request, '/api/governance', governanceBody(fixture.governance.governance_id, 'draft'));
      await page.evaluate(() => window.refreshRegression.refresh());
      const state = page.locator('#refresh-regression > [role="status"]');
      const newestMessage = await state.textContent();
      const newestDisabled = await page.locator('#refresh-regression [name="capture_mode"] option[value="physician_demo"]').isDisabled();
      expect(newestDisabled).toBe(!olderFailure);
      release.release();
      await older;
      await expect(state).toHaveText(newestMessage);
      expect(await page.locator('#refresh-regression [name="capture_mode"] option[value="physician_demo"]').isDisabled()).toBe(newestDisabled);
    } finally {
      release.release();
      await older;
    }
  });
}
