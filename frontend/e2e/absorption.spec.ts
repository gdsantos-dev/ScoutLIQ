import { test, expect, type BrowserContext, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const origin = process.env.E2E_ORIGIN || 'http://localhost:8170';
let auth: Awaited<ReturnType<BrowserContext['storageState']>>;
test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext();
  const response = await context.request.post(`${origin}/api/auth/login`, { data: {
    email: 'e2e@example.test', password: 'E2e-only-not-for-production!',
  } });
  expect(response.ok()).toBeTruthy();
  auth = await context.storageState();
  await context.close();
});
test.beforeEach(async ({ context }) => { await context.addCookies(auth.cookies); });
const record = (name: string) => ({ name, category: 'Cafeteria', city: 'Recife', country: 'BR',
  latitude: -8.065, longitude: -34.876, source_url: 'https://example.org/research',
  claims: [{ statement: 'Informação externa ainda não verificada', source_url: 'https://example.org' }],
});
async function open(page: Page) {
  await page.goto('/#pipeline');
  await page.getByRole('button', { name: 'Absorver pesquisa', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Absorver pesquisa' })).toBeVisible();
}

test('preview, commit, persistent history and canonical Radar without outreach', async ({ page }) => {
  const name = `Café Absorção ${Date.now()}`;
  await open(page);
  await page.getByLabel('Empresas (JSON ou tabela)').fill(JSON.stringify([
    record(name), record(name), { name: 'Pendente QA', category: 'Cafeteria', city: 'Recife' },
  ]));
  await page.getByRole('button', { name: 'Analisar lote' }).click();
  await expect(page.locator('.absorption-summary')).toContainText('1 prontos · 1 pendentes · 1 duplicados');
  await page.getByRole('button', { name: 'Confirmar 1 elegíveis' }).click();
  await expect(page.locator('.absorption-summary')).toContainText('Lote parcialmente absorvido');
  await expect(page.locator('.absorption-summary')).toContainText('1 absorvidos');
  const batches = await page.request.get('/api/absorption/batches').then(r => r.json());
  const batch = await page.request.get(`/api/absorption/batches/${batches[0].id}`).then(r => r.json());
  const leadId = batch.items.find((i: { status: string }) => i.status === 'imported').lead_id;
  const leads = await page.request.get('/api/leads').then(r => r.json());
  expect(leads.filter((l: { name: string }) => l.name === name)).toHaveLength(1);
  expect(leads.find((l: { id: string }) => l.id === leadId).website_status).toBe('unknown');
  const activities = await page.request.get(`/api/leads/${leadId}/activities`).then(r => r.json());
  expect(activities.some((a: { kind: string }) => ['email', 'whatsapp'].includes(a.kind))).toBeFalsy();
  await page.keyboard.press('Escape');
  await page.reload();
  await page.getByRole('button', { name: 'Absorver pesquisa', exact: true }).click();
  await page.getByText('Lotes anteriores', { exact: true }).click();
  await page.locator('.absorption-history button').first().click();
  await expect(page.locator('.absorption-summary')).toContainText('Lote parcialmente absorvido');
  await expect(page.getByRole('button', { name: /Confirmar .* elegíveis/ })).toHaveCount(0);
  await page.screenshot({ path: '../artifacts/absorption-desktop.png' });
  await page.keyboard.press('Escape');
  await page.goto('/#radar');
  await expect(page.getByRole('button', { name: 'Buscar empresas', exact: true })).toBeVisible();
});

test('a lost preview response retries the same request instead of creating another batch', async ({ page }) => {
  await open(page);
  const keys: string[] = [];
  await page.route('**/api/absorption/intake', async route => {
    keys.push(route.request().postDataJSON().request_key);
    if (keys.length === 1) { await route.fetch(); await route.abort('failed'); }
    else await route.continue();
  });
  await page.getByLabel('Empresas (JSON ou tabela)').fill(JSON.stringify([record(`Retry ${Date.now()}`)]));
  await page.getByRole('button', { name: 'Analisar lote' }).click();
  await expect(page.getByRole('alert')).toContainText('Resultado não confirmado');
  await page.getByRole('button', { name: 'Analisar lote' }).click();
  await expect(page.locator('.absorption-summary')).toContainText('Prévia do lote');
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});

for (const width of [320, 390]) {
  test(`mobile ${width}: file, keyboard, overflow and accessible preview`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await open(page);
    await page.getByLabel('Arquivo JSON, CSV ou texto').setInputFiles({ name: 'research.json', mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify([record(`Mobile ${width} ${Date.now()}`)])),
    });
    await page.getByRole('button', { name: 'Analisar lote' }).focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('.absorption-summary')).toContainText('1 prontos');
    const dialog = page.getByRole('dialog', { name: 'Absorver pesquisa' });
    expect(await dialog.evaluate(e => e.scrollWidth <= e.clientWidth + 1)).toBeTruthy();
    const audit = await new AxeBuilder({ page }).include('.absorption-dialog').withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    expect(audit.violations.map(v => ({ id: v.id, targets: v.nodes.map(n => n.target) }))).toEqual([]);
    await page.screenshot({ path: `../artifacts/absorption-${width}.png` });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Absorver pesquisa', exact: true })).toBeFocused();
  });
}

test('invalid JSON and failed history are visible without creating records', async ({ page }) => {
  await page.route('**/api/absorption/batches', route => route.abort('failed'));
  await open(page);
  await expect(page.getByRole('alert')).toContainText('Não foi possível carregar o histórico');
  await page.getByLabel('Empresas (JSON ou tabela)').fill('{invalid');
  await page.getByRole('button', { name: 'Analisar lote' }).click();
  await expect(page.getByRole('alert')).toContainText('não é JSON válido');
  await expect(page.locator('.absorption-preview')).toHaveCount(0);
});
