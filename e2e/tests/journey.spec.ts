import { test, expect } from '@playwright/test';

// Deeper end-to-end journey against a *running* stack with a seeded account.
// Provide credentials to enable it; without them the journey is skipped so the
// smoke suite still runs on a bare stack:
//   E2E_EMAIL=admin@example.com E2E_PASSWORD='ChangeMe!2026' npx playwright test
const EMAIL = process.env.E2E_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;
const haveCreds = Boolean(EMAIL && PASSWORD);

test.describe('authenticated journey', () => {
  test.skip(!haveCreds, 'set E2E_EMAIL and E2E_PASSWORD to run the authenticated journey');

  test('API login issues a token and the studies list is owner-scoped', async ({ request }) => {
    const login = await request.post('/api/v1/auth/login', {
      data: { email: EMAIL, password: PASSWORD },
    });
    expect(login.ok()).toBeTruthy();
    const body = await login.json();
    expect(body.access_token).toBeTruthy();

    // The studies list is per-user: it must accept the token and return an array.
    const studies = await request.get('/api/v1/studies', {
      headers: { Authorization: `Bearer ${body.access_token}` },
    });
    expect(studies.ok()).toBeTruthy();
    expect(Array.isArray(await studies.json())).toBeTruthy();

    // …and reject an unauthenticated caller (owner-scoping now requires identity).
    const anon = await request.get('/api/v1/studies');
    expect(anon.status()).toBe(401);
  });

  test('another curator cannot read a foreign study id', async ({ request }) => {
    const login = await request.post('/api/v1/auth/login', {
      data: { email: EMAIL, password: PASSWORD },
    });
    const { access_token } = await login.json();

    // A study id this account does not own is hidden as 404 (never 403), so a
    // guessed id leaks nothing about whether it exists.
    const foreign = await request.get('/api/v1/mappings/does-not-belong-to-me', {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(foreign.status()).toBe(404);
  });

  test('UI login leaves the login screen', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"], input[name="email"]').first().fill(EMAIL!);
    await page.locator('input[type="password"]').first().fill(PASSWORD!);
    await page.locator('button[type="submit"]').first().click();
    await expect(page).not.toHaveURL(/\/login$/, { timeout: 10_000 });
    await expect(page.locator('#root')).toBeVisible();
  });

  test('UI downloads a bearer-protected harmonized CSV', async ({ page, request }) => {
    test.setTimeout(90_000);
    const login = await request.post('/api/v1/auth/login', {
      data: { email: EMAIL, password: PASSWORD },
    });
    const { access_token } = await login.json();
    const auth = { Authorization: `Bearer ${access_token}` };
    const upload = await request.post('/api/v1/harmonize', {
      headers: auth,
      multipart: {
        file: {
          name: 'download-regression.csv',
          mimeType: 'text/csv',
          buffer: Buffer.from('participant_id,sex\nP001,Female\n'),
        },
        mode: 'schema',
      },
    });
    expect(upload.ok()).toBeTruthy();
    const accepted = await upload.json();

    try {
      await expect.poll(async () => {
        const status = await request.get(`/api/v1/jobs/${accepted.study_id}`, { headers: auth });
        return (await status.json()).state;
      }, { timeout: 60_000 }).toBe('succeeded');

      await page.goto('/login');
      await page.locator('input[type="email"], input[name="email"]').first().fill(EMAIL!);
      await page.locator('input[type="password"]').first().fill(PASSWORD!);
      await page.locator('button[type="submit"]').first().click();
      await expect(page).not.toHaveURL(/\/login$/, { timeout: 10_000 });
      const closeShowcase = page.getByRole('button', { name: 'Close showcase' });
      if (await closeShowcase.isVisible()) await closeShowcase.click();
      await page.goto(`/export/${accepted.study_id}`);

      const responsePromise = page.waitForResponse((response) =>
        response.url().endsWith(`/api/v1/export/${accepted.study_id}/harmonized`),
      );
      const downloadPromise = page.waitForEvent('download');
      await page.getByRole('button', { name: 'Download Harmonized CSV' }).click();
      const response = await responsePromise;
      expect(response.status()).toBe(200);
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toBe(`${accepted.study_id}_harmonized.csv`);
      expect(await download.path()).toBeTruthy();
    } finally {
      await request.delete(`/api/v1/studies/${accepted.study_id}`, { headers: auth });
    }
  });

  test('UI previews the harmonized CSV against the upload', async ({ page, request }) => {
    test.setTimeout(90_000);
    const login = await request.post('/api/v1/auth/login', {
      data: { email: EMAIL, password: PASSWORD },
    });
    const { access_token } = await login.json();
    const auth = { Authorization: `Bearer ${access_token}` };
    const upload = await request.post('/api/v1/harmonize', {
      headers: auth,
      multipart: {
        file: {
          name: 'preview-regression.csv',
          mimeType: 'text/csv',
          buffer: Buffer.from('participant_id,sex\nP001,Female\nP002,NA\n'),
        },
        mode: 'schema',
      },
    });
    expect(upload.ok()).toBeTruthy();
    const accepted = await upload.json();

    try {
      await expect.poll(async () => {
        const status = await request.get(`/api/v1/jobs/${accepted.study_id}`, { headers: auth });
        return (await status.json()).state;
      }, { timeout: 60_000 }).toBe('succeeded');

      // Every uploaded column is accounted for, in upload order, whatever the
      // engine mapped it to; every row is listed by default.
      const preview = await request.get(
        `/api/v1/export/${accepted.study_id}/preview`,
        { headers: auth },
      );
      expect(preview.ok()).toBeTruthy();
      const body = await preview.json();
      expect(body.summary.rows).toBe(2);
      expect(body.columns.map((column: { source: string }) => column.source)).toEqual(['participant_id', 'sex']);
      expect(body.rows.total).toBe(2);

      await page.goto('/login');
      await page.locator('input[type="email"], input[name="email"]').first().fill(EMAIL!);
      await page.locator('input[type="password"]').first().fill(PASSWORD!);
      await page.locator('button[type="submit"]').first().click();
      await expect(page).not.toHaveURL(/\/login$/, { timeout: 10_000 });
      const closeShowcase = page.getByRole('button', { name: 'Close showcase' });
      if (await closeShowcase.isVisible()) await closeShowcase.click();
      await page.goto(`/export/${accepted.study_id}?view=preview`);

      await expect(page.getByRole('tab', { name: /Preview changes/ })).toHaveAttribute('aria-selected', 'true');
      await expect(page.getByRole('heading', { name: 'Harmonized metadata', exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Column changes', exact: true })).toHaveCount(0);
      await expect(page.getByRole('checkbox', { name: 'Changed rows only' })).not.toBeChecked();
      // The grid lists every exported column under its export name, and every row.
      const grid = page.getByRole('region', { name: 'Harmonized metadata table' });
      const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      for (const name of body.rows.columns as string[]) {
        await expect(
          grid.getByRole('columnheader', { name: new RegExp(`^${escape(name)}(\\s*, (renamed|merged) from .+)?$`) }),
        ).toBeVisible();
      }
      await expect(grid.getByRole('rowheader')).toHaveCount(body.rows.total);
      for (const value of body.rows.items[0].values as string[]) {
        await expect(grid.getByRole('cell', { name: value, exact: true }).first()).toBeVisible();
      }
      // The Columns checklist lists every exported column, all shown by default.
      const picker = page.getByRole('button', { name: /^Columns/ });
      await expect(picker).toContainText('All');
      await picker.click();
      for (const name of body.rows.columns as string[]) {
        await expect(page.getByRole('checkbox', { name, exact: true })).toBeChecked();
      }
      await page.keyboard.press('Escape');
      await expect(picker).toHaveAttribute('aria-expanded', 'false');

      // Switching back to Downloads keeps the study and drops the view param.
      await page.getByRole('tab', { name: /Downloads/ }).click();
      await expect(page).toHaveURL(new RegExp(`/export/${accepted.study_id}$`));
      await expect(page.getByRole('button', { name: 'Download Harmonized CSV' })).toBeVisible();
    } finally {
      await request.delete(`/api/v1/studies/${accepted.study_id}`, { headers: auth });
    }
  });

  test('UI keeps a column merged from many long names inside the column list', async ({ page, request }) => {
    test.setTimeout(90_000);
    const login = await request.post('/api/v1/auth/login', {
      data: { email: EMAIL, password: PASSWORD },
    });
    const { access_token } = await login.json();
    const auth = { Authorization: `Bearer ${access_token}` };
    // Spellings of one long name: every engine maps them to the same field.
    const names = [
      'GLUTAMATE_DECARBOXYLASE_2_ANTIBODY_TITRE',
      'Glutamate_Decarboxylase_2_Antibody_Titre',
      'glutamate_decarboxylase_2_antibody_titre',
      'Glutamate_decarboxylase_2_antibody_titre',
      'GLUTAMATE_decarboxylase_2_antibody_titre',
    ];
    const upload = await request.post('/api/v1/harmonize', {
      headers: auth,
      multipart: {
        file: {
          name: 'wide-merge-regression.csv',
          mimeType: 'text/csv',
          buffer: Buffer.from(`participant_id,${names.join(',')}\nP001,1,2,3,4,5\nP002,6,7,8,9,10\n`),
        },
        mode: 'schema',
      },
    });
    expect(upload.ok()).toBeTruthy();
    const accepted = await upload.json();

    try {
      await expect.poll(async () => {
        const status = await request.get(`/api/v1/jobs/${accepted.study_id}`, { headers: auth });
        return (await status.json()).state;
      }, { timeout: 60_000 }).toBe('succeeded');
      const body = await (
        await request.get(`/api/v1/export/${accepted.study_id}/preview`, { headers: auth })
      ).json();
      const merged = body.columns.filter((column: { action: string }) => column.action === 'merged');
      expect(merged.map((column: { source: string }) => column.source)).toEqual(names);

      await page.goto('/login');
      await page.locator('input[type="email"], input[name="email"]').first().fill(EMAIL!);
      await page.locator('input[type="password"]').first().fill(PASSWORD!);
      await page.locator('button[type="submit"]').first().click();
      await expect(page).not.toHaveURL(/\/login$/, { timeout: 10_000 });
      const closeShowcase = page.getByRole('button', { name: 'Close showcase' });
      if (await closeShowcase.isVisible()) await closeShowcase.click();
      await page.goto(`/export/${accepted.study_id}?view=preview`);

      // The header names two columns and how many more, on one capped line.
      const grid = page.getByRole('region', { name: 'Harmonized metadata table' });
      const header = grid.getByRole('columnheader', { name: new RegExp(`^${merged[0].target}\\s*, merged from 5 columns`) });
      await expect(header).toContainText(`${names[0]} + ${names[1]} + 3 more`);
      expect((await header.locator('span[aria-hidden="true"]').boundingBox())!.width).toBeLessThanOrEqual(300);

      // Nothing in the checklist extends past the dropdown.
      await page.getByRole('button', { name: /^Columns/ }).click();
      const list = page.getByRole('group', { name: 'Columns to show' });
      await expect(list.getByRole('checkbox', { name: merged[0].target, exact: true })).toHaveAccessibleDescription(
        `merged from 5 columns: ${names[0]}, ${names[1]} and 3 more`,
      );
      const overflowing = await list.evaluate((fieldset) => {
        const panel = (fieldset.parentElement as HTMLElement).getBoundingClientRect();
        return [...fieldset.querySelectorAll('*')].filter((el) => el.getBoundingClientRect().right > panel.right + 1)
          .length;
      });
      expect(overflowing).toBe(0);
    } finally {
      await request.delete(`/api/v1/studies/${accepted.study_id}`, { headers: auth });
    }
  });
});
