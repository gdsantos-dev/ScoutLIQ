const ORIGIN = process.env.E2E_ORIGIN || 'http://localhost:8001';
import { test, expect, type Page, type BrowserContext } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import path from 'node:path';

let auth: Awaited<ReturnType<BrowserContext['storageState']>>;
test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext();
  const response = await context.request.post(`${ORIGIN}/api/auth/login`, { data: { email: 'e2e@example.test', password: 'E2e-only-not-for-production!' } });
  expect(response.ok(), await response.text()).toBeTruthy();
  auth = await context.storageState();
  await context.close();
});
test.beforeEach(async ({ context }) => { await context.addCookies(auth.cookies); });

async function preparePage(page: Page, waitForWorkflow = true) {
  const csrf = (await page.request.get('/api/auth/me').then(r => r.json())).csrf;
  const name = `Oficina Horizonte ${Date.now()}`;
  const created = await page.request.post('/api/leads', { headers: { 'X-CSRF-Token': csrf, Origin: ORIGIN }, data: {
    name, category: 'Oficina', city: 'Recife', country: 'BR', latitude: -8.05, longitude: -34.9,
    website: 'https://example.org', website_status: 'unknown', whatsapp: '5581999999999',
  } });
  const lead = await created.json();
  expect(created.status()).toBe(201);
  const moved = await page.request.patch(`/api/leads/${lead.id}/stage`, { headers: { 'X-CSRF-Token': csrf, Origin: ORIGIN }, data: { version: lead.version, stage: 'discovered' } });
  expect(moved.ok()).toBeTruthy();
  await page.goto('/#pipeline');
  await page.getByText(name, { exact: true }).first().click();
  await expect(page.locator('dialog[open]')).toBeVisible();
  await page.getByRole('tab', { name: 'Operação', exact: true }).click();
  if (waitForWorkflow) await expect(page.getByRole('region', { name: 'Ficha operacional' })).toBeVisible();
  return { lead, csrf, name };
}

test('evidence, draft, approval and CRM persist without a send', async ({ page }) => {
  const { lead } = await preparePage(page);
  await page.getByText('Registrar observação com fonte', { exact: true }).click();
  await page.getByRole('combobox', { name: 'Categoria da evidência' }).click();
  await page.getByRole('option', { name: 'Conteúdo e navegação', exact: true }).click();
  await page.getByLabel('Escopo da observação').fill('Somente a página de menu conferida neste teste.');
  await page.getByLabel('Observação', { exact: true }).fill('O menu publicado está disponível somente em PDF.');
  await page.getByLabel('URL da fonte').fill('https://example.org/menu');
  await page.getByRole('button', { name: 'Registrar evidência', exact: true }).click();
  await expect(page.getByText('Evidência registrada como não verificada.')).toBeVisible();
  await page.locator('.op-evidence > summary').click();
  await page.getByRole('combobox', { name: 'Classificação da evidência' }).click();
  await page.getByRole('option', { name: 'Confirmada', exact: true }).click();
  await page.getByLabel('Justificativa da revisão').fill('Conferido manualmente na página do menu.');
  await page.getByRole('button', { name: 'Salvar revisão' }).click();
  await expect(page.getByText('1/1 confirmadas e válidas')).toBeVisible();
  await page.getByRole('button', {name:'Abordagem',exact:true}).click();
  await page.getByText('Preparar nova abordagem', { exact: true }).click();
  await page.getByLabel('Destinatário', { exact: true }).fill('contact@example.org');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Preparar rascunho', exact: true }).click();
  await expect(page.getByLabel('Mensagem', { exact: true })).toHaveValue(/somente em PDF/);
  await page.getByLabel('Nota da revisão (opcional)').fill('Autorização fictícia registrada no teste local.');
  await page.getByRole('button', { name: 'Aprovar conteúdo' }).click();
  await expect(page.locator('.op-approved')).toContainText('Nenhum envio realizado');
  await page.evaluate(() => Promise.all(document.getAnimations().map(a => a.finished.catch(() => {}))));
  await page.screenshot({ path: '../artifacts/workflow-desktop.png' });
  await page.locator('.context-body').evaluate(element => element.scrollTo({ top: 0 }));
  await page.screenshot({ path: '../artifacts/workflow-overview.png' });
  const audit = await new AxeBuilder({ page }).include('.op-workflow').withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(audit.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) }))).toEqual([]);
  await page.reload();
  await page.getByText((await page.request.get('/api/leads').then(r => r.json())).find((l: { id: string }) => l.id === lead.id).name, { exact: true }).first().click();
  await page.getByRole('tab', { name: 'Operação', exact: true }).click();
  await expect(page.locator('.op-approved')).toBeVisible();
  await page.getByLabel('Mensagem', { exact: true }).fill('Mensagem revisada durante o teste de persistência.');
  await expect(page.getByText('Alterações não salvas.', { exact: false })).toBeVisible();
  await page.getByRole('tab', { name: 'Pesquisa', exact: true }).click();
  await page.getByRole('tab', { name: 'Operação', exact: true }).click();
  await expect(page.getByLabel('Mensagem', { exact: true })).toHaveValue('Mensagem revisada durante o teste de persistência.');
  await page.getByRole('button', { name: 'Salvar alterações' }).click();
  await expect(page.getByRole('button', { name: 'Aprovar conteúdo' })).toBeVisible();
  const history = await page.request.get(`/api/leads/${lead.id}/activities`).then(r => r.json());
  expect(history.some((a: { kind: string }) => a.kind === 'email')).toBeFalsy();
  expect(history.some((a: { metadata: { event?: string } }) => a.metadata.event === 'outreach_approved')).toBeTruthy();
  const samples: number[] = [];
  for (let i = 0; i < 12; i++) {
    const start = performance.now();
    const result = await page.request.get(`/api/leads/${lead.id}/workflow`);
    expect(result.ok()).toBeTruthy();
    samples.push(performance.now() - start);
  }
  samples.sort((a, b) => a - b);
  await writeFile('../artifacts/workflow-performance.json', JSON.stringify({
    scenario: 'Local SQLite, one evidence and one draft; no external provider',
    samples_ms: samples, median_ms: samples[6], p95_ms: samples[11],
  }, null, 2));
});

test('mobile widths, keyboard, reduced motion and empty state', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await preparePage(page);
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => Promise.all(document.getAnimations().map(a => a.finished.catch(() => {}))));
    await expect(page.getByText('Nenhuma evidência registrada.', { exact: false })).toBeVisible();
    const overflow = await page.evaluate(() => {
      const elements = [document.documentElement, document.querySelector('.context-body')!, document.querySelector('.op-workflow')!];
      return elements.map(e => ({ scroll: e.scrollWidth, client: e.clientWidth }));
    });
    expect(overflow.every(e => e.scroll <= e.client + 1), JSON.stringify(overflow)).toBeTruthy();
    if (width === 390) await page.screenshot({ path: '../artifacts/workflow-mobile.png' });
  }
  await page.getByRole('tab', { name: 'Operação', exact: true }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: 'Análise', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('dialog[open]')).toHaveCount(0);
});

test('server error and retry are visible without false success', async ({ page }) => {
  await page.route('**/api/leads/*/workflow', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Falha controlada para teste.' }) }));
  await preparePage(page, false);
  await expect(page.getByText('Falha controlada para teste.')).toBeVisible();
  await page.unroute('**/api/leads/*/workflow');
  await page.getByRole('button', { name: 'Tentar novamente', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Ficha operacional' })).toBeVisible();
});

test('server worker finishes a controlled batch after closing the page', async ({ page, context }) => {
  test.setTimeout(90000);
  const { lead, csrf } = await preparePage(page);
  const ids = [lead.id];
  const headers = { 'X-CSRF-Token': csrf, Origin: ORIGIN };
  for (let i = 0; i < 2; i++) {
    const response = await page.request.post('/api/leads', { headers, data: {
      name: `Background controlled ${i} ${Date.now()}`, category: 'Oficina', city: 'Recife', country: 'BR',
      latitude: -8.05, longitude: -34.9, website: 'https://example.org', website_status: 'unknown',
    } });
    expect(response.status()).toBe(201); ids.push((await response.json()).id);
  }
  const response = await page.request.post('/api/research/batches', { headers, data: { lead_ids: ids, mode: 'web', stale_days: 0 } });
  expect(response.status()).toBe(201);
  const { batch } = await response.json();
  expect(batch.total).toBe(3);
  expect(batch.execution_mode).toBe('worker');
  await page.close();
  const python = process.env.E2E_PYTHON;
  expect(python, 'Set E2E_PYTHON to the isolated Python runtime').toBeTruthy();
  await new Promise<void>((resolve, reject) => {
    const child = spawn(python!, ['tests/worker_browser_fixture.py'], { cwd: path.resolve('..'), windowsHide: true, stdio: 'ignore' });
    child.on('error', reject);
    child.on('exit', code => code === 0 ? resolve() : reject(new Error(`Controlled worker exit ${code}`)));
  });
  const reopened = await context.newPage();
  await reopened.goto('/');
  const persisted = await reopened.request.get(`/api/research/batches/${batch.id}`).then(r => r.json());
  expect(persisted.batch.done).toBe(3);
  expect(persisted.batch.status).toBe('completed');
  const evidence = await reopened.request.get(`/api/leads/${lead.id}/workflow`).then(r => r.json());
  expect(evidence.evidence.some((e: { observation_key: string }) => e.observation_key === 'viewport')).toBeTruthy();
  await writeFile('../artifacts/background-browser-proof.json', JSON.stringify({ batch_id: batch.id, page_closed_before_worker: true, processed: persisted.batch.processed, total: persisted.batch.total, status: persisted.batch.status, provider: 'controlled fixture; no network' }, null, 2));
});

test('concurrent draft edits preserve local text and allow explicit recovery', async ({ page }) => {
  const { lead, csrf } = await preparePage(page);
  await page.getByRole('button', {name:'Abordagem',exact:true}).click();
  await page.getByText('Preparar nova abordagem', { exact: true }).click();
  await page.getByRole('combobox', { name: 'Estratégia da abordagem' }).click();
  await page.getByRole('option', { name: 'Apresentação inicial', exact: true }).click();
  await page.getByLabel('Destinatário', { exact: true }).fill('review@example.org');
  await page.getByRole('button', { name: 'Preparar rascunho', exact: true }).click();
  await expect(page.getByLabel('Mensagem', { exact: true })).toBeVisible();
  const base = `/api/leads/${lead.id}`;
  const draft = (await page.request.get(base + '/workflow').then(r => r.json())).drafts[0];
  const changed = await page.request.put(`${base}/outreach/drafts/${draft.id}`, {
    headers: { 'X-CSRF-Token': csrf, Origin: ORIGIN },
    data: { version: draft.version, subject: draft.subject, body: 'Texto salvo em outra sessão para testar concorrência.' },
  });
  expect(changed.status()).toBe(200);
  const local = 'Texto local preservado após o conflito de versão.';
  await page.getByLabel('Mensagem', { exact: true }).fill(local);
  await page.getByRole('button', { name: 'Salvar alterações', exact: true }).click();
  await expect(page.getByText('O rascunho mudou no servidor.', { exact: false })).toBeVisible();
  await expect(page.getByLabel('Mensagem', { exact: true })).toHaveValue(local);
  await page.getByRole('button', { name: 'Manter meu texto sobre a versão atual', exact: true }).click();
  await page.getByRole('button', { name: 'Salvar alterações', exact: true }).click();
  await expect(page.getByText('Alterações não salvas.', { exact: false })).toHaveCount(0);
  const saved = (await page.request.get(base + '/workflow').then(r => r.json())).drafts[0];
  expect(saved.body).toBe(local);
});
