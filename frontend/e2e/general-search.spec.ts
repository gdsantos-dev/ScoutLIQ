import { test, expect, type BrowserContext, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

let auth: Awaited<ReturnType<BrowserContext['storageState']>>;
test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext();
  const response = await context.request.post(`${process.env.E2E_ORIGIN}/api/auth/login`, {
    data: { email: 'e2e@example.test', password: 'E2e-only-not-for-production!' },
  });
  expect(response.ok()).toBeTruthy();
  auth = await context.storageState();
  await context.close();
  await mkdir('../artifacts/v1381', { recursive: true });
});
test.beforeEach(async ({ page }) => {
  await page.context().addCookies(auth.cookies);
  await page.goto('/#radar');
});
async function form(page: Page) {
  await page.getByRole('button', { name: 'Buscar empresas', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Buscar empresas' });
  await dialog.getByRole('combobox', { name: 'Onde?' }).fill('Recife');
  await dialog.getByRole('listbox').getByRole('option').click();
  return dialog;
}
async function worker(page: Page) {
  const root = path.resolve('..');
  await new Promise<void>((resolve, reject) => {
    const child = spawn(process.env.E2E_PYTHON || path.resolve(root, '../../../.venv/Scripts/python.exe'),
      ['tests/unified_browser_fixture.py', 'worker'], {
        cwd: root, windowsHide: true, env: { ...process.env, E2E_PORT: new URL(page.url()).port },
      });
    let output = '';
    child.stdout.on('data', b => output += b);
    child.stderr.on('data', b => output += b);
    child.on('error', reject);
    child.on('close', code => code === 0 ? resolve() : reject(new Error(output)));
  });
}

test('empty query runs broad discovery through worker and restores saved general intent', async ({ page }) => {
  test.setTimeout(120000);
  const dialog = await form(page);
  await expect(dialog.getByLabel('O que buscar (opcional)')).toHaveValue('');
  for (const value of ['25', '50', '75', '100']) {
    await dialog.getByLabel('Quantidade', { exact: true }).selectOption(value);
    await expect(dialog.getByRole('button', { name: 'Buscar empresas', exact: true })).toBeEnabled();
  }
  await dialog.getByLabel('Quantidade', { exact: true }).selectOption('50');
  const launch = page.waitForResponse(r => r.url().endsWith('/smart-searches/launch'));
  await dialog.getByRole('button', { name: 'Buscar empresas', exact: true }).click();
  const started = (await (await launch).json()).job;
  expect(started.intent.search_mode).toBe('general');
  expect(started.intent.sectors).toEqual([]);
  await expect(dialog).toHaveCount(0);
  await worker(page);
  await page.reload();
  const progress = page.getByRole('region', { name: 'Busca em andamento' });
  await expect(progress).toContainText('Exploração geral');
  await expect(progress).toContainText('Resultado parcial');
  await expect(progress).toContainText('2 / 50 qualificadas');
  await expect(page.getByRole('button', { name: 'Abrir Café QA Geral', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Abrir Barbearia QA Geral', exact: true })).toBeVisible();
  const result = await (await page.request.get(`/api/smart-searches/${started.id}`)).json();
  expect(result.diversity.categories).toBe(2);
  expect(result.results.find((r: { name: string }) => r.name === 'Starbucks QA Geral').group).toBe('discarded');
  await page.screenshot({ path: '../artifacts/v1381/general-results-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '../artifacts/v1381/general-results-mobile.png', fullPage: true });
  await progress.getByRole('button', { name: 'Salvar busca', exact: true }).click();
  await progress.getByLabel('Nome da busca').fill('QA geral Recife');
  await progress.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(progress.getByRole('button', { name: 'Busca salva', exact: true })).toBeDisabled();
  await page.reload();
  await page.getByRole('button', { name: 'Buscas salvas', exact: true }).click();
  const saved = page.getByRole('dialog', { name: 'Buscas salvas' }).getByRole('button', { name: /^QA geral Recife/ });
  await expect(saved).toContainText('Exploração geral');
  await saved.click();
  await expect(dialog.getByLabel('O que buscar (opcional)')).toHaveValue('');
  await expect(dialog.getByLabel('Quantidade', { exact: true })).toHaveValue('50');
  await expect(dialog.getByRole('combobox', { name: 'Onde?' })).toHaveValue('Recife, Pernambuco, Brasil');
  await page.keyboard.press('Escape');
  await page.getByText('Buscas recentes', { exact: true }).click();
  await expect(page.locator('.search-history')).toContainText('Exploração geral');
});

test('optional niches, filters, responsive form, keyboard and accessibility', async ({ page }) => {
  const dialog = await form(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const measures = [];
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.screenshot({ path: `../artifacts/v1381/general-form-${width}.png` });
    const size = await dialog.evaluate(e => ({ width: e.clientWidth, scroll: e.scrollWidth }));
    expect(size.scroll).toBeLessThanOrEqual(size.width + 1);
    measures.push({ viewport: width, ...size });
  }
  await dialog.getByRole('button', { name: 'Ajustar critérios', exact: true }).click();
  const criteria = dialog.getByRole('region', { name: 'Ajustar critérios' });
  const niches = criteria.getByRole('group', { name: 'Nichos opcionais (até 4)' });
  expect(await niches.getByRole('checkbox', { checked: true }).count()).toBe(0);
  await criteria.getByRole('group', { name: 'Preferências', exact: true }).getByLabel('Instagram disponível').check();
  await page.screenshot({ path: '../artifacts/v1381/general-criteria-mobile.png' });
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  await writeFile('../artifacts/v1381/accessibility.json', JSON.stringify({ measures, violations: audit.violations }, null, 2));
  expect(audit.violations).toEqual([]);
  const launch = page.waitForResponse(r => r.url().endsWith('/smart-searches/launch'));
  await dialog.getByRole('button', { name: 'Buscar empresas', exact: true }).click();
  const job = (await (await launch).json()).job;
  expect(job.intent.search_mode).toBe('filtered');
  expect(job.intent.sectors).toEqual([]);
  expect(job.intent.preferences).toContain('instagram');
  const progress = page.getByRole('region', { name: 'Busca em andamento' });
  await progress.getByRole('button', { name: 'Cancelar busca' }).click();
  await expect(progress).toContainText('Cancelada');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await form(page);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Buscar empresas', exact: true })).toBeFocused();
});

test('unknown one-character text cannot silently start a general search', async ({ page }) => {
  const dialog = await form(page);
  await dialog.getByLabel('O que buscar (opcional)').fill('x');
  const launched = page.waitForResponse(r => r.url().endsWith('/smart-searches/launch'));
  await dialog.getByRole('button', { name: 'Buscar empresas', exact: true }).click();
  expect((await (await launched).json()).status).toBe('clarification');
  await expect(dialog.getByRole('alert')).toBeVisible();
  await expect(dialog).toBeVisible();
});
