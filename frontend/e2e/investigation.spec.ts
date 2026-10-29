import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { spawn } from "node:child_process";
import path from "node:path";
let auth: Awaited<ReturnType<BrowserContext["storageState"]>>;
let headers: Record<string, string>;
const origin = process.env.E2E_ORIGIN || "http://localhost:8500";
test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext();
  const response = await context.request.post(`${origin}/api/auth/login`, {
    data: {
      email: "e2e@example.test",
      password: "E2e-only-not-for-production!",
    },
  });
  expect(response.ok()).toBeTruthy();
  headers = { "X-CSRF-Token": (await response.json()).csrf, Origin: origin };
  auth = await context.storageState();
  await context.close();
});
test.beforeEach(async ({ context }) => {
  await context.addCookies(auth.cookies);
});
async function worker() {
  await new Promise<void>((resolve, reject) => {
    const child = spawn(
      process.env.E2E_PYTHON || "python",
      ["tests/unified_browser_fixture.py", "worker"],
      { cwd: path.resolve(".."), env: process.env, windowsHide: true },
    );
    let output = "";
    child.stderr.on("data", (v) => (output += v));
    child.on("error", reject);
    child.on("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(output)),
    );
  });
}
async function create(page: Page, name: string) {
  const response = await page.request.post("/api/leads", {
    headers,
    data: {
      name,
      category: "Cafeteria",
      city: "Recife",
      country: "BR",
      latitude: -8.05,
      longitude: -34.9,
      phone: "5581999999999",
      website_status: "unknown",
    },
  });
  expect(response.status()).toBe(201);
  return response.json();
}
test("manual selection, queued arrival, pause/resume and commercial review on desktop", async ({
  page,
}) => {
  const first = await create(page, "Café Investigação Primeiro");
  const second = await create(page, "Café Investigação Segundo");
  await page.goto("/#radar");
  await page
    .getByRole("checkbox", {
      name: `Selecionar ${first.name} para investigação`,
    })
    .check();
  await expect(page.locator('.investigation-selection input').first()).toHaveCSS('height', '18px');
  await expect(page.locator('.investigation-selection').first()).toHaveCSS('height', '44px');
  await page.getByPlaceholder("Filtrar empresas…").fill(second.name);
  await page
    .getByRole("button", { name: "Investigar selecionadas (1)" })
    .click();
  await expect(page.locator(".radar-agent")).toContainText("0/1");
  await page.getByPlaceholder("Filtrar empresas…").fill("");
  await page
    .locator(".radar-agent")
    .getByRole("button", { name: "Pausar", exact: true })
    .click();
  await expect(page.locator(".radar-agent")).toContainText("pausada");
  const response = await page.request.post("/api/investigation/requests", {
    headers,
    data: { lead_ids: [second.id], request_key: crypto.randomUUID() },
  });
  expect(response.status()).toBe(201);
  await page
    .locator(".radar-agent")
    .getByRole("button", { name: "Continuar", exact: true })
    .click();
  await worker();
  await expect(page.locator(".radar-agent")).toContainText(
    "Investigação concluída",
    { timeout: 20000 },
  );
  await page
    .getByText("Resultados e motivos de prioridade", { exact: true })
    .click();
  await expect(page.locator(".investigation-results")).toContainText("Score");
  await expect(page.locator(".investigation-results")).toContainText(
    "Confiança",
  );
  expect(
    (
      await new AxeBuilder({ page })
        .include(".investigation-results")
        .withTags(["wcag2a", "wcag2aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await expect(page.getByLabel("Fila de investigação").locator('option:checked')).toContainText('Concluído');
  await page.screenshot({
    path: "../artifacts/investigation-desktop.png",
    fullPage: true,
  });
  await page.reload();
  const queue = page.getByLabel("Fila de investigação");
  await expect(queue.locator("option")).toHaveCount(3);
  const values = await queue
    .locator("option")
    .evaluateAll((options) =>
      options.map((o) => (o as HTMLOptionElement).value).filter(Boolean),
    );
  await queue.selectOption(values[0]);
  await expect(page.locator(".radar-agent")).toContainText("concluída");
});
test("explicit opt-in settings persist at 320px", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 900 });
  await page.goto("/#settings");
  const panel = page.locator("section").filter({
    has: page.getByRole("heading", {
      name: "Investigação automática",
      exact: true,
    }),
  });
  await expect(panel.getByLabel("Novas empresas da Busca")).not.toBeChecked();
  await panel.getByLabel("Novas empresas da Busca").check();
  await panel.getByLabel("Empresas confirmadas na Absorção").check();
  await panel.getByLabel("Empresas por lote", { exact: true }).fill("5");
  await panel.getByRole("button", { name: "Salvar investigação" }).click();
  await expect(panel.getByRole("status")).toContainText("salvas");
  await page.reload();
  await expect(panel.getByLabel("Novas empresas da Busca")).toBeChecked();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  expect(
    (
      await new AxeBuilder({ page })
        .include(".settings-layout")
        .withTags(["wcag2a", "wcag2aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await panel.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "../artifacts/investigation-settings-320.png",
    fullPage: true,
  });
});
test("absorption opt-in schedules once and manual action reuses pending work on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const result = await page.request.post("/api/absorption/preview", {
    headers,
    data: {
      source: "manual",
      request_key: crypto.randomUUID(),
      records: [
        {
          name: "Café Absorção Investigação",
          category: "Cafeteria",
          city: "Recife",
          country: "BR",
          latitude: -8.2,
          longitude: -34.8,
          phone: "5581999999999",
        },
      ],
    },
  });
  expect(result.status()).toBe(201);
  const batch = await result.json();
  const committed = await page.request.post(
    `/api/absorption/batches/${batch.id}/commit`,
    { headers, data: { payload_hash: batch.payload_hash, confirm: true } },
  );
  expect(committed.ok()).toBeTruthy();
  await page.goto("/#pipeline");
  await page
    .getByRole("button", { name: "Absorver pesquisa", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Absorver pesquisa" });
  // Open persistent batch from existing history.
  await dialog.getByText("Lotes anteriores", { exact: true }).click();
  await dialog
    .getByRole("button", { name: /manual/ })
    .first()
    .click();
  await dialog
    .getByRole("button", { name: "Investigar empresas absorvidas" })
    .click();
  await expect(
    dialog.getByText("Investigação agendada.", { exact: false }),
  ).toBeVisible();
  await page.goto("/#radar");
  await expect(page.getByLabel("Fila de investigação")).toBeVisible();
  await worker();
  await page.reload();
  const queue = page.getByLabel("Fila de investigação");
  await expect(queue.locator("option")).toHaveCount(5);
  const options = await queue
    .locator("option")
    .evaluateAll((o) =>
      o.map((v) => (v as HTMLOptionElement).value).filter(Boolean),
    );
  await queue.selectOption(options[1]);
  await page
    .getByText("Resultados e motivos de prioridade", { exact: true })
    .click();
  await expect(page.locator(".investigation-results")).toContainText(
    "Café Absorção Investigação",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../artifacts/investigation-390.png",
    fullPage: true,
  });
});
