import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { spawn } from "node:child_process";
import path from "node:path";
const origin = process.env.E2E_ORIGIN || "http://localhost:8290";
let auth: Awaited<ReturnType<BrowserContext["storageState"]>>;
test.beforeAll(async ({ browser }) => {
  const c = await browser.newContext();
  const r = await c.request.post(`${origin}/api/auth/login`, {
    data: {
      email: "e2e@example.test",
      password: "E2e-only-not-for-production!",
    },
  });
  expect(r.ok()).toBeTruthy();
  auth = await c.storageState();
  await c.close();
});
test.beforeEach(async ({ context }) => {
  await context.addCookies(auth.cookies);
});
async function open(page: Page) {
  await page.goto("/#pipeline");
  await page
    .getByRole("button", { name: "Absorver pesquisa", exact: true })
    .click();
}
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
const row = (name: string) => ({
  name,
  category: "Cafeteria",
  city: "Recife",
  country: "BR",
  address: "Rua Azul, 10",
});

test("CSV mapping, partial commit, correction and incremental confirmation at 320px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 900 });
  await open(page);
  const stamp = Date.now();
  const raw = `Nome;Categoria;Cidade;País;Latitude;Longitude;URL\nPrimeira ${stamp};Cafeteria;Recife;Brasil;-8,05;-34,9;example.org\nSegunda ${stamp};Cafeteria;Recife;BR;;;example.net`;
  await page
    .getByLabel("Arquivo JSON, CSV ou texto")
    .setInputFiles({
      name: "empresas.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("\ufeff" + raw),
    });
  await page.getByRole("button", { name: "Analisar lote" }).click();
  await expect(
    page.getByRole("group", { name: "Mapear colunas" }),
  ).toBeVisible();
  await page
    .getByLabel("Destino de URL", { exact: true })
    .selectOption("website");
  await page.getByRole("button", { name: "Conferir mapeamento" }).click();
  await expect(page.locator(".absorption-summary")).toContainText(
    "1 prontos · 1 pendentes",
  );
  await page.getByRole("button", { name: "Confirmar 1 elegíveis" }).click();
  await expect(page.locator(".absorption-summary")).toContainText(
    "Lote parcialmente absorvido",
  );
  await page.getByRole("button", { name: `Revisar Segunda ${stamp}` }).click();
  await page.getByLabel("Latitude", { exact: true }).fill("-8.07");
  await page.getByLabel("Longitude", { exact: true }).fill("-34.88");
  await page
    .getByLabel("Justificativa da revisão")
    .fill("Coordenadas conferidas na pesquisa.");
  const dialog = page.getByRole("dialog", { name: "Absorver pesquisa" });
  expect(
    await dialog.evaluate((e) => e.scrollWidth <= e.clientWidth + 1),
  ).toBeTruthy();
  const audit = await new AxeBuilder({ page })
    .include(".absorption-dialog")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(audit.violations.map((v) => v.id)).toEqual([]);
  await page.getByRole("button", { name: "Salvar correção" }).click();
  await page.locator(".absorption-summary").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "../artifacts/absorption-intelligent-320.png",
  });
  await page.getByRole("button", { name: "Confirmar 1 elegíveis" }).click();
  await expect(page.locator(".absorption-summary")).toContainText(
    "2 absorvidos",
  );
  await page.keyboard.press("Escape");
  await open(page);
  await page.getByText("Lotes anteriores", { exact: true }).click();
  await page.locator(".absorption-history button").first().click();
  await expect(page.locator(".absorption-summary")).toContainText(
    "2 absorvidos",
  );
});

test("persistent worker recovery pauses, resumes and fills POI without auto import", async ({
  page,
}) => {
  await open(page);
  const name = `Recuperar ${Date.now()}`;
  await page
    .getByLabel("Empresas (JSON ou tabela)")
    .fill(JSON.stringify([row(name)]));
  await page.getByRole("button", { name: "Analisar lote" }).click();
  await page.getByLabel("Permitir consultas à fonte configurada").check();
  await page.getByRole("button", { name: "Completar pendências" }).click();
  await expect(
    page.getByText("Na fila do worker", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pausar recuperação" }).click();
  await expect(page.getByText("Pausada", { exact: true })).toBeVisible();
  await worker();
  await page.getByRole("button", { name: "Retomar recuperação" }).click();
  await worker();
  await page.getByRole("button", { name: "Atualizar lote" }).click();
  await expect(page.locator(".absorption-summary")).toContainText("1 prontos");
  await expect(page.locator(".absorption-summary")).toContainText(
    "0 absorvidos",
  );
  await page.locator(".absorption-summary").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "../artifacts/absorption-intelligent-desktop.png",
  });
  await page.getByRole("button", { name: `Revisar ${name}` }).click();
  await page
    .getByText("Original e histórico de alterações", { exact: true })
    .click();
  await expect(page.locator(".absorption-editor pre")).toContainText(
    "fixture-poi-1",
  );
  const audit = await new AxeBuilder({ page })
    .include(".absorption-dialog")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(audit.violations.map((v) => v.id)).toEqual([]);
});

test("ambiguous company requires justified decision; rejects and later accepts safely", async ({
  page,
}) => {
  await open(page);
  const name = `Ambigua ${Date.now()}`;
  await page
    .getByLabel("Empresas (JSON ou tabela)")
    .fill(JSON.stringify([row(name)]));
  await page.getByRole("button", { name: "Analisar lote" }).click();
  await page.getByLabel("Permitir consultas à fonte configurada").check();
  await page.getByRole("button", { name: "Completar pendências" }).click();
  await expect(
    page.getByText("Na fila do worker", { exact: true }),
  ).toBeVisible();
  await worker();
  await page.getByRole("button", { name: "Atualizar lote" }).click();
  await page.getByRole("button", { name: `Revisar ${name}` }).click();
  await expect(page.locator(".absorption-suggestion")).toHaveCount(2);
  await expect(
    page.getByRole("button", { name: "Aceitar localização" }).first(),
  ).toBeDisabled();
  await page
    .getByLabel("Justificativa da revisão")
    .fill("A primeira pesquisa não confirma a unidade.");
  await page.getByRole("button", { name: "Rejeitar sugestão" }).first().click();
  await expect(page.locator(".absorption-summary")).toContainText(
    "1 pendentes",
  );
  await page.getByRole("button", { name: "Completar pendências" }).click();
  await worker();
  await page.getByRole("button", { name: "Atualizar lote" }).click();
  await page.getByRole("button", { name: `Revisar ${name}` }).click();
  await page
    .getByLabel("Justificativa da revisão")
    .fill("Conferi a unidade e o endereço completo.");
  await page
    .getByRole("button", { name: "Aceitar localização" })
    .first()
    .click();
  await expect(page.locator(".absorption-summary")).toContainText("1 prontos");
  await expect(page.locator(".absorption-summary")).toContainText(
    "0 absorvidos",
  );
});

test("table unknown column requires mapping, local row errors and cancellation persist", async ({
  page,
}) => {
  await open(page);
  await page
    .getByLabel("Empresas (JSON ou tabela)")
    .fill(
      `Nome\tCidade\tPaís\tCoisa\nIncompleta ${Date.now()}\tRecife\tBR\tignorar`,
    );
  await page.getByRole("button", { name: "Analisar lote" }).click();
  await page.getByLabel("Destino de Coisa").selectOption("ignore");
  await page.getByRole("button", { name: "Conferir mapeamento" }).click();
  await expect(page.locator(".absorption-summary")).toContainText(
    "1 pendentes",
  );
  await page.getByRole("button", { name: "Completar pendências" }).click();
  await page.getByRole("button", { name: "Cancelar recuperação" }).click();
  await worker();
  await page.getByRole("button", { name: "Atualizar lote" }).click();
  await expect(page.getByText("Cancelada", { exact: true })).toBeVisible();
  await expect(page.locator(".absorption-summary")).toContainText(
    "0 absorvidos",
  );
});
