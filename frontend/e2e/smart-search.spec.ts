import { test, expect, type BrowserContext } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { spawn } from "node:child_process";
import path from "node:path";
let authState: Awaited<ReturnType<BrowserContext["storageState"]>>;
let headers: Record<string, string>;

test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext();
  const origin = process.env.E2E_ORIGIN || "http://localhost:8077";
  const login = await context.request.post(`${origin}/api/auth/login`, {
    data: {
      email: "e2e@example.test",
      password: "E2e-only-not-for-production!",
    },
  });
  expect(login.ok()).toBeTruthy();
  headers = { "X-CSRF-Token": (await login.json()).csrf, Origin: origin };
  authState = await context.storageState();
  await context.close();
});
test.beforeEach(async ({ page }) => {
  await page.context().addCookies(authState.cookies);
  await page.goto("/#radar");
  await page
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
});

test("editable intent, all targets, mobile reflow and keyboard", async ({
  page,
}) => {
  const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
  await dialog
    .getByLabel("O que buscar (opcional)")
    .fill("Clínicas odontológicas com WhatsApp");
  await dialog.getByRole("combobox", { name: "Onde?" }).fill("Recife");
  await dialog.getByRole("listbox").getByRole("option").click();
  await dialog
    .getByRole("button", { name: "Ajustar critérios", exact: true })
    .click();
  const criteria = dialog.getByRole("region", { name: "Ajustar critérios" });
  const required = criteria.getByRole("group", {
    name: "Requisitos obrigatórios",
    exact: true,
  });
  await expect(
    required.getByRole("checkbox", { name: "WhatsApp disponível" }),
  ).toBeChecked();
  await required.getByRole("checkbox", { name: "Telefone disponível" }).check();
  for (const target of ["25", "50", "75", "100"]) {
    await dialog.getByLabel("Quantidade", { exact: true }).selectOption(target);
    await expect(
      dialog.getByRole("button", { name: "Buscar empresas", exact: true }),
    ).toBeEnabled();
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    const size = await dialog.evaluate((e) => ({
      scroll: e.scrollWidth,
      width: e.clientWidth,
    }));
    expect(size.scroll).toBeLessThanOrEqual(size.width + 1);
    if (width === 390)
      await page.screenshot({ path: "../artifacts/smart-search-mobile.png" });
  }
  expect(
    (
      await new AxeBuilder({ page })
        .include(".unified-search")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: "../artifacts/smart-search-desktop.png" });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("job survives closed browser and returns audited result groups", async ({
  page,
  context,
}) => {
  test.setTimeout(90000);
  const existing = (await (await page.request.get("/api/leads")).json()) as {
    id: string;
    name: string;
  }[];
  for (const lead of existing.filter((l) =>
    [
      "Clínica QA Aurora",
      "Clínica QA Horizonte",
      "Starbucks QA Centro",
    ].includes(l.name),
  ))
    expect(
      (await page.request.delete(`/api/leads/${lead.id}`, { headers })).ok(),
    ).toBeTruthy();
  const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
  await dialog.getByLabel("O que buscar (opcional)").fill("Clínicas odontológicas");
  await dialog.getByRole("combobox", { name: "Onde?" }).fill("Recife");
  await dialog.getByRole("listbox").getByRole("option").click();
  await dialog.getByLabel("Quantidade", { exact: true }).selectOption("25");
  const launched = page.waitForResponse(
    (r) =>
      r.url().endsWith("/smart-searches/launch") &&
      r.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  const job = (await (await launched).json()).job;
  expect(job.status).toBe("pending");
  await page.close();
  const root = path.resolve("..");
  const python =
    process.env.E2E_PYTHON ||
    path.resolve(root, "../../../.venv/Scripts/python.exe");
  await new Promise<void>((resolve, reject) => {
    const child = spawn(
      python,
      ["tests/unified_browser_fixture.py", "worker"],
      { cwd: root, windowsHide: true, stdio: "ignore" },
    );
    child.on("error", reject);
    child.on("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(`worker ${code}`)),
    );
  });
  const reopened = await context.newPage();
  await reopened.goto("/#radar");
  const progress = reopened.getByRole("region", { name: "Busca em andamento" });
  await expect(progress).toContainText("Resultado parcial");
  const persisted = await (
    await reopened.request.get("/api/smart-searches/" + job.id)
  ).json();
  expect(persisted.counters).toMatchObject({
    qualified: 2,
    discarded: 1,
    investigated: 2,
  });
  expect(persisted.plan.steps[0].pages).toBe(1);
  await progress.getByText("Detalhes da execução", { exact: true }).click();
  await expect(
    progress.getByText(persisted.plan.decision, { exact: true }),
  ).toBeVisible();
  await expect(
    progress
      .locator("dl > div")
      .filter({ hasText: "Páginas coletadas / limite" })
      .locator("dd"),
  ).toHaveText(
    `${persisted.counters.calls} / ${persisted.limits.provider_pages}`,
  );
  await expect(
    reopened.getByRole("button", {
      name: "Abrir Clínica QA Aurora",
      exact: true,
    }),
  ).toBeVisible();
  await progress.getByLabel("Exibir resultados").selectOption("discarded");
  await reopened
    .getByRole("button", { name: "Abrir Starbucks QA Centro", exact: true })
    .click();
  await reopened.getByRole("tab", { name: "Análise", exact: true }).click();
  const review = reopened.getByRole("region", { name: "Revisão comercial" });
  await review
    .getByRole("button", { name: "Revisar dados comerciais" })
    .click();
  await review
    .getByLabel("Autonomia", { exact: true })
    .selectOption("independent");
  await review.getByLabel("Operação", { exact: true }).selectOption("active");
  await review
    .getByLabel("Natureza", { exact: true })
    .selectOption("commercial");
  await review
    .getByLabel("Evidência e motivo")
    .fill("Autonomia confirmada em fixture sintética de validação.");
  await review.getByRole("button", { name: "Registrar revisão" }).click();
  await expect(review.getByRole("status")).toHaveText("Revisão registrada.");
  await reopened.keyboard.press("Escape");
  await expect(progress).toContainText("1 em investigação");
  await progress.getByLabel("Exibir resultados").selectOption("investigating");
  await expect(
    reopened.getByRole("button", {
      name: "Abrir Starbucks QA Centro",
      exact: true,
    }),
  ).toBeVisible();
  await progress
    .getByRole("button", { name: "Salvar busca", exact: true })
    .click();
  const name = "QA busca unificada " + Date.now();
  await progress.getByLabel("Nome da busca").fill(name);
  await progress.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(
    progress.getByRole("button", { name: "Busca salva", exact: true }),
  ).toBeDisabled();
  const saved = (
    await (await reopened.request.get("/api/radar/saved-searches")).json()
  ).find((s: { name: string }) => s.name === name);
  expect(saved.query.commercial_intent).toEqual(job.intent);
  await reopened.screenshot({ path: "../artifacts/smart-search-result.png" });
  expect(
    (
      await reopened.request.delete("/api/radar/saved-searches/" + saved.id, {
        headers,
      })
    ).ok(),
  ).toBeTruthy();
});

test("input errors remain visible without executing a search", async ({
  page,
}) => {
  const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
  let launches = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/smart-searches/launch"))
      launches++;
  });
  await page.route("**/api/smart-searches/prepare", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Falha controlada de interpretação." }),
    }),
  );
  await dialog
    .getByLabel("O que buscar (opcional)")
    .fill("Tecnologia nos Estados Unidos");
  await dialog
    .getByRole("button", { name: "Ajustar critérios", exact: true })
    .click();
  await expect(dialog.getByRole("alert")).toContainText(
    "Falha controlada de interpretação.",
  );
  await page.unroute("**/api/smart-searches/prepare");
  await dialog
    .getByRole("button", { name: "Ajustar critérios", exact: true })
    .click();
  await expect(
    dialog.getByRole("region", { name: "Ajustar critérios" }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Buscar empresas", exact: true }),
  ).toBeDisabled();
  expect(launches).toBe(0);
});
