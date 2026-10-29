import { execFileSync } from "node:child_process";
import path from "node:path";
const ORIGIN = process.env.E2E_ORIGIN || 'http://localhost:8001';
import { test, expect } from "@playwright/test";
import type { Page, BrowserContext } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import type {
  Lead,
  User,
  Campaign,
  LeadResearch,
  LeadAudit,
  LeadResearchResponse,
  LeadEnrichmentResponse,
  LeadReanalysisResponse,
} from "../src/types";

let auth: Awaited<ReturnType<BrowserContext["storageState"]>>;
const errors: string[] = [],
  output = "../artifacts/redesign";
async function choose(
  page: Page,
  name: string | RegExp,
  option: string | RegExp,
) {
  await page
    .getByRole("combobox", { name, exact: typeof name === "string" })
    .click();
  await page
    .getByRole("option", { name: option, exact: typeof option === "string" })
    .click();
}
async function nav(page: Page, name: string) {
  const toggle = page.locator('button[aria-controls="workspace-destinations"]');
  if (await toggle.isVisible() && await toggle.getAttribute('aria-expanded') === 'false') await toggle.click();
  const navigationName = name === 'Negociações' ? /^(Negociações|Pipeline)$/ : name === 'Sites / Entregas' ? /^(Sites \/ Entregas|Entregas)$/ : name;
  await page
    .getByRole("navigation", { name: "Navegação principal" })
    .getByRole("button", { name: navigationName, exact: true })
    .click();
  await expect(page.locator("#main-content h1")).toHaveText(
    name === "Sites / Entregas" ? "Sites" : name,
  );
  await expect(page.locator(".loading-view")).toHaveCount(0);
  await expect(page.getByTestId("page-view")).toHaveCSS("opacity", "1");
  if (name === "Financeiro")
    await expect(
      page.locator(".trend-chart svg.recharts-surface"),
    ).toBeVisible();
}
async function globalPage(page: Page, name: string) {
  await page.getByRole("button", { name: "Menu do workspace" }).click();
  await page
    .locator(".workspace-menu")
    .getByRole("button", { name, exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name, exact: true }).first(),
  ).toBeVisible();
}
async function noOverflow(page: Page) {
  const size = await page.evaluate(() => ({
    width: innerWidth,
    actual: document.documentElement.scrollWidth,
  }));
  expect(size.actual).toBeLessThanOrEqual(size.width + 1);
  for (const dialog of await page.locator("dialog[open]").all()) {
    const box = await dialog.boundingBox();
    expect(box?.x).toBeGreaterThanOrEqual(0);
    expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(
      size.width + 1,
    );
  }
}
async function accessible(page: Page) {
  // Route motion also uses JS-driven opacity, outside document.getAnimations().
  await expect(page.locator('.loading-view')).toHaveCount(0);
  if (await page.locator('.product-shell').count())
    await expect(page.getByTestId('page-view')).toHaveCSS('opacity','1');
  else
    await expect(page.getByRole('main')).toBeVisible();
  await page.evaluate(() => Promise.all(document.getAnimations().filter(animation => animation.effect?.getTiming().iterations !== Infinity).map(animation => animation.finished.catch(() => {}))));
  const audit = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    audit.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
}
async function writeApi<T>(
  page: Page,
  path: string,
  data: unknown,
  method = "POST",
): Promise<T> {
  const session = (await (await page.request.get("/api/auth/me")).json()) as {
    csrf: string;
  };
  const response = await page.request.fetch(`/api${path}`, {
    method,
    data,
    headers: { "X-CSRF-Token": session.csrf, Origin: ORIGIN },
  });
  expect(response.ok(), `${method} ${path}: ${response.status()}`).toBeTruthy();
  return (await response.json()) as T;
}
async function testLead(page: Page, prefix: string): Promise<Lead> {
  return writeApi<Lead>(page, "/leads", {
    name: `${prefix} ${Date.now()}`,
    category: "Cafeteria",
    city: "Recife",
    country: "BR",
    address: "Rua de teste, 123",
    latitude: -8.06,
    longitude: -34.9,
    website_status: "none",
    potential_cents: 250000,
  });
}
test.beforeAll(async ({ browser }) => {
  await mkdir(output, { recursive: true });
  const context = await browser.newContext({ locale: "pt-BR" }),
    page = await context.newPage();
  try {
    const cached = JSON.parse(await readFile('../artifacts/e2e-auth-synthetic.json', 'utf8')) as typeof auth;
    await context.addCookies(cached.cookies);
    if ((await context.request.get(`${ORIGIN}/api/auth/me`)).ok()) {
      auth = cached; await context.close(); return;
    }
    await context.clearCookies();
  } catch { /* First worker authenticates; replacement workers reuse only the test session. */ }
  await page.goto(ORIGIN);
  await page.getByLabel("E-mail", { exact: true }).fill("e2e@example.test");
  await page
    .getByLabel("Senha", { exact: true })
    .fill("E2e-only-not-for-production!");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page.locator(".product-shell")).toBeVisible();
  auth = await context.storageState();
  await writeFile('../artifacts/e2e-auth-synthetic.json', JSON.stringify(auth));
  await context.close();
});
test.beforeEach(async ({ context, page }) => {
  errors.length = 0;
  page.on("pageerror", (error) => errors.push(error.message));
  await context.addCookies(auth.cookies);
  await page.goto("/");
  await expect(page.locator(".radar-results")).toBeVisible();
});
test.afterEach(async () => {
  expect(errors).toEqual([]);
});

test("desktop: environments, all destinations, accessibility", async ({
  page,
}) => {
  test.setTimeout(180000);
  await page.getByRole("button", {name:"Ver mapa",exact:true}).click();
  await expect(page.locator(".map-shell")).toHaveAttribute(
    "data-ready",
    "true",
  );
  await expect(page.locator(".map-marker").first()).toBeVisible();
  await accessible(page);
  await page.screenshot({
    path: `${output}/radar-desktop.png`,
    fullPage: true,
  });
  for (const name of ["Oportunidades", "Monitores", "Campanhas"]) {
    await nav(page, name);
    await accessible(page);
    await noOverflow(page);
    await page.screenshot({
      path: `${output}/${name}-desktop.png`,
      fullPage: true,
    });
  }
  await page
    .getByRole("button", { name: "Gerir clientes", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ações", exact: true }),
  ).toBeVisible();
  for (const name of [
    "Ações",
    "Negociações",
    "Clientes",
    "Sites / Entregas",
    "Financeiro",
  ]) {
    await nav(page, name);
    await accessible(page);
    await noOverflow(page);
    await page.screenshot({
      path: `${output}/${name.replace(" / ", "-")}-desktop.png`,
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Operar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Campanhas", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Gerir clientes", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Financeiro", exact: true }),
  ).toBeVisible();
  for (const name of ["Automações", "Configurações"]) {
    await globalPage(page, name);
    await accessible(page);
  }
});

test("v1.26 action queue: management opens on execution surface", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Gerir clientes", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Ações", exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: /Hoje/ })).toBeVisible();
  await expect(page.getByRole("tab", { name: /Atrasadas/ })).toBeVisible();
  await expect(page.getByRole("tab", { name: /Próximas/ })).toBeVisible();
  await noOverflow(page);
  await accessible(page);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await noOverflow(page);
  await accessible(page);
  await page.screenshot({ path: `${output}/actions-mobile.png`, fullPage: true });
});

test("v1.25 visual polish: quiet shell, fields and responsive navigation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.reload();
  await expect(page.locator(".environment-dot")).toHaveCount(0);
  await expect(page.locator("body")).toHaveCSS("background-image", "none");
  await expect(page.locator(".workspace-masthead").first()).toHaveCSS(
    "border-bottom-width",
    "0px",
  );
  await expect(page.locator(".environment-switch")).toHaveCSS(
    "box-shadow",
    "none",
  );

  await page.getByRole("button", { name: "Gerir clientes", exact: true }).click();
  await nav(page, "Clientes");
  await expect(page.getByLabel("Buscar cliente")).toHaveCSS(
    "background-color",
    "rgba(0, 0, 0, 0)",
  );
  await noOverflow(page);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.locator(".workspace-masthead")).toHaveCSS(
    "backdrop-filter",
    "none",
  );
  await expect(page.locator(".workspace-navigation")).toHaveCSS(
    "backdrop-filter",
    "none",
  );
  await noOverflow(page);
});

test("context: progressive data, keyboard tabs, focus and Escape", async ({
  page,
}) => {
  const opener = page.getByRole("button", {
    name: "Abrir Café do Pátio",
    exact: true,
  });
  await opener.click();
  const panel = page.locator(".context-panel");
  await expect(panel).toBeVisible();
  await expect(panel.locator(".analysis-workspace")).toHaveCount(0);
  await accessible(page);
  await page.screenshot({ path: `${output}/context-summary.png` });
  await panel.getByRole("tab", { name: "Análise", exact: true }).click();
  await expect(
    panel.getByText("Confiança dos dados", { exact: true }),
  ).toBeVisible();
  await accessible(page);
  await panel
    .getByRole("tab", { name: "Análise", exact: true })
    .press("ArrowRight");
  await expect(
    panel.getByRole("tab", { name: "Pesquisa", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await panel.getByRole("tab", { name: "Pesquisa", exact: true }).press("End");
  await expect(
    panel.getByRole("tab", { name: "Relacionamento", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("commands: accent-insensitive search, Enter and natural-search handoff", async ({
  page,
}) => {
  await page.keyboard.press("Control+k");
  const input = page.locator(".command-input input");
  await input.fill("cafe do patio");
  await expect(
    page.getByRole("option").filter({ hasText: "Café do Pátio" }),
  ).toBeVisible();
  await input.press("Enter");
  await expect(
    page.getByRole("dialog", { name: "Café do Pátio" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.keyboard.press("Control+k");
  await input.fill("dentistas sem site em Recife");
  await input.press("Enter");
  await expect(
    page.getByRole("dialog", { name: "Buscar empresas", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "O que buscar (opcional)", exact: true }),
  ).toHaveValue("dentistas sem site em Recife");
  await page.keyboard.press("Escape");
  await page.keyboard.press("/");
  await expect(
    page.getByRole("dialog", { name: "Buscar empresas", exact: true }),
  ).toBeVisible();
});

test("filters: custom select in dialog, reset and empty state", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Filtros", exact: true }).click();
  await accessible(page);
  await choose(page, "Lista inteligente", "Sem site");
  await page
    .getByRole("button", { name: "Ver resultados", exact: true })
    .click();
  await page
    .getByLabel("Filtrar estabelecimentos encontrados")
    .fill("inexistente-zxq");
  await expect(page.locator(".radar-results .empty")).toBeVisible();
  await page.getByLabel("Filtrar estabelecimentos encontrados").fill("");
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await page
    .getByRole("button", { name: "Limpar filtros", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Ver resultados", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Abrir Café do Pátio", exact: true }),
  ).toBeVisible();
});

test("mobile radar: list-first, contextual map and progressive context", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.locator(".surface-radar.ledger-mode")).toBeVisible();
  await page.getByRole("button", {name:"Ver mapa",exact:true}).click();
  const radar = page.locator(".surface-radar.canvas-mode");
  await expect(radar).toBeVisible();
  await expect(radar).toHaveClass(/sheet-peek/);
  await expect(page.locator(".radar-map")).toBeVisible();
  await expect(page.getByRole("button", { name: "Filtros", exact: true })).toBeVisible();
  await noOverflow(page);
  await accessible(page);

  await expect(page.getByLabel("Filtrar estabelecimentos encontrados")).toBeVisible();
  await page.getByRole("button", {name:"Ver lista",exact:true}).click();
  await expect(page.locator(".radar-map")).toHaveCount(0);
  await expect(page.locator(".radar-results-footer")).toBeVisible();

  await page.getByRole("button", { name: "Buscar empresas", exact: true }).click();
  await expect(page.locator("dialog.unified-search")).toBeVisible();
  await noOverflow(page);
  await page.getByRole("button", { name: "Fechar", exact: true }).click();

  await page.getByRole("button", { name: /^Filtros/ }).click();
  await expect(page.locator("dialog.radar-filter-sheet")).toBeVisible();
  await noOverflow(page);
  await page.getByRole("button", { name: "Fechar", exact: true }).click();

  await page.getByRole("button", { name: "Abrir Café do Pátio", exact: true }).click();
  const context = page.locator(".context-panel");
  await expect(context).toBeVisible();
  await expect(context).not.toHaveClass(/context-mobile-expanded/);
  await expect(context.getByRole("tab", { name: "Análise", exact: true })).toBeHidden();
  await context.getByRole("button", { name: "Expandir detalhes", exact: true }).click();
  await expect(context).toHaveClass(/context-mobile-expanded/);
  await expect(context.getByRole("tab", { name: "Análise", exact: true })).toBeVisible();
  await context.getByRole("button", { name: "Recolher detalhes", exact: true }).click();
  await expect(context).not.toHaveClass(/context-mobile-expanded/);
  await noOverflow(page);
  await accessible(page);
});

test("mobile remaining modules: opportunities, monitors, campaigns, automations, settings and about", async ({
  page,
}) => {
  test.setTimeout(120000);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/#opportunities");
  await expect(page.getByRole("heading", { name: "Oportunidades", exact: true })).toBeVisible();
  await expect(page.locator(".surface-opportunities .opportunity-row").first()).toBeVisible();
  await noOverflow(page);

  await page.goto("/#monitors");
  await expect(page.getByRole("heading", { name: "Monitores", exact: true })).toBeVisible();
  await expect(page.locator(".surface-monitors .monitor-overview")).toBeVisible();
  await noOverflow(page);

  await page.goto("/#campaigns");
  await expect(page.getByRole("heading", { name: "Campanhas", exact: true })).toBeVisible();
  await expect(page.locator(".campaign-workspace, .empty")).toBeVisible();
  await noOverflow(page);

  await page.goto("/#automations");
  await expect(page.getByRole("heading", { name: "Automações", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Nova automação", exact: true }).click();
  await expect(page.locator(".automation-builder")).toBeVisible();
  await expect(page.locator(".automation-builder")).toHaveCSS("position", "fixed");
  await noOverflow(page);
  await page.getByRole("button", { name: "Fechar", exact: true }).click();

  await page.goto("/#settings");
  await expect(page.getByRole("heading", { name: "Configurações", exact: true })).toBeVisible();
  await expect(page.locator(".settings-layout")).toBeVisible();
  await noOverflow(page);

  await page.goto("/#about");
  await expect(page.getByRole("heading", { name: "Sobre o ScoutLIQ", exact: true })).toBeVisible();
  await expect(page.locator(".about-hero")).toBeVisible();
  await noOverflow(page);
});

test("real workflow: lead, watchlist, action, contact, sale, payment, cost and export", async ({
  page,
}) => {
  test.setTimeout(120000);
  const name = `Validação Café ${Date.now()}`;
  await page
    .getByRole("button", { name: "Adicionar estabelecimento", exact: true })
    .click();
  for (const [label, value] of [
    ["Empresa", name],
    ["Categoria", "Cafeteria"],
    ["Cidade", "Recife"],
    ["Latitude", "-8.06"],
    ["Longitude", "-34.90"],
  ])
    await page.getByLabel(label, { exact: true }).fill(value);
  await choose(page, /Situação do site/, "Sem site confirmado");
  await page.getByLabel(/Valor potencial/).fill("2500");
  await accessible(page);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Adicionar estabelecimento", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByLabel("Filtrar estabelecimentos encontrados").fill(name);
  await page
    .getByRole("button", { name: `Abrir ${name}`, exact: true })
    .click();
  await page
    .getByRole("button", { name: "Acompanhar empresa", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Parar de acompanhar", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Salvar oportunidade", exact: true })
    .click();
  await page.getByRole("tab", { name: "Relacionamento", exact: true }).click();
  await page
    .getByLabel("Próxima ação", { exact: true })
    .fill("Enviar proposta de site");
  await page
    .getByRole("button", { name: "Data da próxima ação", exact: true })
    .click();
  await page
    .locator(".date-popover")
    .getByRole("button", { name: "Hoje", exact: true })
    .click();
  await page.getByRole("button", { name: "Salvar ação", exact: true }).click();
  await page.getByLabel("Detalhes do contato").fill("Cliente pediu proposta");
  await page.getByRole("button", { name: "Registrar", exact: true }).click();
  await expect(page.locator(".commercial-timeline")).toContainText(
    "Cliente pediu proposta",
  );
  await page
    .getByRole("button", { name: "Abrir negociação", exact: true })
    .click();
  await expect(page.locator(".context-panel")).toHaveClass(/context-manage/);
  await page.keyboard.press("Escape");
  await page.getByLabel("Buscar negociação", { exact: true }).fill(name);
  await choose(page, `Mover ${name}`, "Negociando");
  await expect(
    page.getByRole("combobox", { name: `Mover ${name}` }),
  ).toContainText("Negociando");
  await choose(page, `Mover ${name}`, "Fechado");
  await page.getByLabel("Serviço vendido").fill("Site institucional");
  await page
    .getByRole("button", { name: "Concluir venda", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await nav(page, "Clientes");
  await page.getByLabel("Buscar cliente").fill(name);
  await page
    .getByRole("button", { name: `Abrir ${name}`, exact: true })
    .click();
  await page
    .getByRole("button", { name: "Registrar recebimento", exact: true })
    .click();
  await page.getByLabel(/Valor recebido/).fill("1000");
  await page
    .getByRole("button", { name: "Salvar recebimento", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await page.getByLabel("Buscar cliente").fill(name);
  await expect(page.locator("tbody tr")).toContainText("1.000,00");
  await nav(page, "Financeiro");
  await page
    .getByRole("button", { name: "Registrar custo", exact: true })
    .click();
  await page
    .getByLabel("Descrição", { exact: true })
    .fill(`Hospedagem ${name}`);
  await page.getByLabel("Valor", { exact: true }).fill("100");
  await page.getByRole("button", { name: "Salvar custo", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Custos", exact: true }).click();
  await expect(page.locator("tbody")).toContainText(`Hospedagem ${name}`);
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Exportar dados", exact: true })
    .click();
  expect((await download).suggestedFilename()).toMatch(/scoutliq.*\.json/);
});

test("mobile management: native lists replace desktop tables", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await page.getByRole("button", { name: "Gerir clientes", exact: true }).click();

  await nav(page, "Negociações");
  await expect(page.locator(".negotiation-list")).toBeVisible();
  await noOverflow(page);

  await nav(page, "Clientes");
  await expect(page.locator(".client-mobile-list")).toBeVisible();
  await expect(page.locator(".management-desktop-table").first()).toBeHidden();
  await noOverflow(page);

  await nav(page, "Sites / Entregas");
  await expect(page.locator(".site-mobile-list")).toBeVisible();
  await expect(page.locator(".management-desktop-table").first()).toBeHidden();
  await noOverflow(page);

  await nav(page, "Financeiro");
  await expect(page.locator(".finance-mobile-ledger")).toBeVisible();
  await expect(page.locator(".management-desktop-table").first()).toBeHidden();
  await noOverflow(page);
  await accessible(page);
});

for (const width of [320, 375, 390, 393, 430, 768, 1920])
  test(`responsive ${width}: navigation, map sheet, forms and context`, async ({
    page,
  }) => {
    test.setTimeout(120000);
    await page.setViewportSize({ width, height: width >= 768 ? 1080 : 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute(
      "data-motion",
      "reduced",
    );
    await expect(page.locator(".radar-results")).toBeVisible();
    await noOverflow(page);
    await accessible(page);
    if (width <= 430) {
      await page.getByRole("button", {name:"Ver mapa",exact:true}).click();
  await expect(page.locator(".map-shell")).toHaveAttribute(
        "data-ready",
        "true",
      );
      const credits = await page
        .locator(".maplibregl-ctrl-attrib")
        .boundingBox();
      const results = await page.locator(".radar-results").boundingBox();
      expect(credits).not.toBeNull();
      expect((credits?.y ?? 0) + (credits?.height ?? 0)).toBeLessThanOrEqual(
        results?.y ?? 0,
      );
    }
    if (width <= 430) await page.getByRole("button", { name: "Ver lista", exact: true }).click();
    await page
      .getByRole("button", { name: "Abrir Café do Pátio", exact: true })
      .click();
    await noOverflow(page);
    await accessible(page);
    await page.screenshot({
      path: `${output}/context-${width}.png`,
      fullPage: true,
    });
    await page.keyboard.press("Escape");
    for (const name of ["Oportunidades", "Monitores", "Campanhas"]) {
      await nav(page, name);
      await noOverflow(page);
      if (width === 320) await accessible(page);
    }
    await page
      .getByRole("button", { name: "Gerir clientes", exact: true })
      .click();
    for (const name of [
      "Ações",
      "Negociações",
      "Clientes",
      "Sites / Entregas",
      "Financeiro",
    ]) {
      await nav(page, name);
      await noOverflow(page);
      if (width === 320) await accessible(page);
    }
    await page.screenshot({
      path: `${output}/finance-${width}.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Registrar custo", exact: true })
      .click();
    await noOverflow(page);
    await accessible(page);
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Operar", exact: true }).click();
    await nav(page, "Radar");
    await page.screenshot({
      path: `${output}/radar-${width}.png`,
      fullPage: true,
    });
  });

test("sites: create, calendar, edit, reload, mobile detail and remove test record", async ({
  page,
}) => {
  const name = `Site Validação ${Date.now()}`;
  await page
    .getByRole("button", { name: "Gerir clientes", exact: true })
    .click();
  await nav(page, "Sites / Entregas");
  await page.getByRole("button", { name: "Novo site", exact: true }).click();
  await page.getByRole("combobox", { name: "Cliente", exact: true }).click();
  await page
    .getByRole("option")
    .filter({ hasNotText: "Selecionar cliente" })
    .first()
    .click();
  await page.getByLabel("Nome do site", { exact: true }).fill(name);
  await page.getByLabel("Domínio", { exact: true }).fill("example.com");
  await page.getByLabel("Titular do domínio").fill("Cliente de teste");
  await page
    .getByRole("button", { name: "Renovação do domínio", exact: true })
    .click();
  await page
    .locator(".date-popover")
    .getByRole("button", { name: "Hoje", exact: true })
    .click();
  await choose(page, "Status do site", "Ativo");
  await page.getByLabel(/Receita mensal/).fill("149");
  await page.getByLabel(/Custo mensal/).fill("29");
  await accessible(page);
  await page.getByRole("button", { name: "Salvar site", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await page.getByLabel("Buscar site").fill(name);
  await expect(page.locator("tbody")).toContainText("120,00");
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await page.getByRole("button", { name: "Editar site", exact: true }).click();
  await page
    .getByLabel("Hospedagem", { exact: true })
    .fill("Servidor de teste");
  await page.getByRole("button", { name: "Salvar site", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await expect(page.getByRole("dialog")).toContainText("Servidor de teste");
  await noOverflow(page);
  await page.screenshot({
    path: `${output}/site-detail-mobile.png`,
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Excluir registro", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Excluir registro", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Nenhum site encontrado", exact: true }),
  ).toBeVisible();
});

test("failure states: API retry, offline notice and session expiry", async ({
  page,
  context,
}) => {
  await page.route("**/api/leads", (route) => route.abort("failed"));
  await page
    .getByRole("button", { name: "Atualizar dados", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("conexão");
  await page.unroute("**/api/leads");
  await page
    .getByRole("button", { name: "Tentar novamente", exact: true })
    .click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await context.setOffline(true);
  await expect(page.locator(".connection-notice")).toBeVisible();
  await context.setOffline(false);
  await expect(page.locator(".connection-notice")).toHaveCount(0);
  await page.route("**/api/leads", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: '{"detail":"Sessão expirada"}',
    }),
  );
  await page
    .getByRole("button", { name: "Atualizar dados", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Entrar", exact: true }),
  ).toBeVisible();
});

test("saved searches: area query, persisted monitor and opportunities isolation", async ({ page }) => {
  test.setTimeout(90000);
  const name = `Monitor ${Date.now()}`;
  const bounds = [-34.94, -8.09, -34.86, -8.01];
  const savedRow = await writeApi<{id:string}>(page, "/radar/saved-searches", {name, query:{location:"Recife",country:"BR",category:"Clínica odontológica",scope:"bounds",radius_km:7,center_lat:-8.05,center_lng:-34.9,bounds}});
  let legacyRequests=0;
  page.on('request',r=>{if(r.method()==='POST' && r.url().endsWith('/api/radar/search')) legacyRequests++;});
  await page.reload();
  await page.getByRole("button", {name:"Ver mapa",exact:true}).click();
  await expect(page.locator('.map-shell')).toHaveAttribute('data-ready','true');
  await page.getByRole('button',{name:'Buscar nesta área visível',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Buscar empresas',exact:true})).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Buscas salvas',exact:true}).click();
  const saved=page.locator('.radar-saved-search-item').filter({hasText:name});
  await saved.getByRole('button',{name:'Monitorar',exact:true}).click();
  await choose(page,`Frequência do monitoramento ${name}`,'Semanal');
  await expect(saved.getByRole('combobox')).toContainText('Semanal');
  await page.keyboard.press('Escape');
  await nav(page,'Monitores');
  await expect(saved).toContainText('Semanal');
  await page.reload();
  await expect(saved).toContainText('Semanal');
  await nav(page,'Oportunidades');
  await expect(page.locator('.opportunity-row').first()).toBeVisible();
  await page.getByRole('button',{name:'Buscas salvas',exact:true}).click();
  await saved.locator('.radar-saved-search-run').click();
  await expect(page.getByRole('dialog')).toHaveCount(1);
  let records=await page.request.get('/api/radar/saved-searches').then(r=>r.json());
  expect(records.find((r:{id:string})=>r.id===savedRow.id).next_monitor_at).toBeGreaterThan(0);
  await saved.getByRole('button',{name:`Desativar monitoramento ${name}`,exact:true}).click();
  const started=page.waitForResponse(r=>r.url().endsWith(`/smart-searches/saved/${savedRow.id}/launch`) && r.request().method()==='POST');
  await saved.locator('.radar-saved-search-run').click();
  const response=await started;expect(response.ok(),await response.text()).toBeTruthy();
  const job=(await response.json()).job;
  expect(job.intent.legacy.bounds).toEqual(bounds);
  expect(job.intent.legacy.category).toBe('Clínica odontológica');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Busca em andamento'})).toBeVisible();
  execFileSync(process.env.E2E_PYTHON!,['tests/unified_browser_fixture.py','worker'],{cwd:path.resolve('..'),windowsHide:true});
  await page.reload();
  await expect(page.getByRole('region',{name:'Busca em andamento'})).toContainText('Resultado parcial');
  const completed=await page.request.get(`/api/smart-searches/${job.id}`).then(r=>r.json());
  expect(completed.results.length).toBeGreaterThan(0);
  records=await page.request.get('/api/radar/saved-searches').then(r=>r.json());
  expect(records.find((r:{id:string})=>r.id===savedRow.id).last_result_ids.sort()).toEqual(completed.results.map((r:{id:string})=>r.id).sort());
  expect(legacyRequests).toBe(0);
});

test("campaigns and automations: real CRUD, membership, status and command deep link", async ({
  page,
}) => {
  test.setTimeout(120000);
  const lead = await testLead(page, "Campanha");
  await page.reload();
  await nav(page, "Campanhas");
  await page
    .getByRole("button", { name: "Nova campanha", exact: true })
    .click();
  await page.getByLabel("Nome", { exact: true }).fill(lead.name);
  await page
    .getByLabel("Descrição", { exact: true })
    .fill("Empresas sem site em Recife");
  await accessible(page);
  await page
    .getByRole("button", { name: "Criar campanha", exact: true })
    .click();
  await expect(page.locator(".campaign-detail h2")).toHaveText(lead.name);
  await choose(page, "Adicionar empresa", `${lead.name} · Recife`);
  await page.getByRole("button", { name: "Adicionar", exact: true }).click();
  await expect(page.locator(".campaign-member-list")).toContainText(lead.name);
  await choose(page, "Status da campanha", "Pausada");
  await expect(
    page.getByRole("combobox", { name: "Status da campanha" }),
  ).toContainText("Pausada");
  await accessible(page);
  await page.screenshot({
    path: `${output}/campaign-active.png`,
    fullPage: true,
  });
  const alternate = await writeApi<Campaign>(page, "/campaigns", {
    name: `Outra ${Date.now()}`,
    status: "active",
  });
  await page.keyboard.press("Control+k");
  await page.locator(".command-input input").fill(alternate.name);
  await expect(
    page
      .getByRole("option")
      .filter({ hasText: alternate.name })
      .filter({ hasText: "Campanha" }),
  ).toBeVisible();
  await page.locator(".command-input input").press("Enter");
  await expect(page.locator(".campaign-detail h2")).toHaveText(alternate.name);
  await globalPage(page, "Automações");
  await page
    .getByRole("button", { name: "Nova automação", exact: true })
    .click();
  await page.getByLabel("Nome da automação", { exact: true }).fill(lead.name);
  await choose(page, "Quando", "Execução manual");
  await page
    .getByRole("button", { name: "Remover condição", exact: true })
    .click();
  await page
    .getByLabel("Texto da ação", { exact: true })
    .fill("Revisar oportunidade de teste");
  await accessible(page);
  await noOverflow(page);
  await page
    .getByRole("button", { name: "Salvar automação", exact: true })
    .click();
  const row = page.locator(".automation-row").filter({ hasText: lead.name });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Pausar", exact: true }).click();
  await expect(
    row.getByRole("button", { name: "Ativar", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page
      .locator(".automation-row")
      .filter({ hasText: lead.name })
      .getByRole("button", { name: "Ativar", exact: true }),
  ).toBeVisible();
  await accessible(page);
  await page.setViewportSize({ width: 320, height: 844 });
  await noOverflow(page);
  await accessible(page);
});

test("large result sets: progressive list, bounded markers and no page overflow", async ({
  page,
}) => {
  const source = (
    (await (await page.request.get("/api/leads")).json()) as Lead[]
  )[0];
  const leads: Lead[] = Array.from({ length: 2000 }, (_, i) => ({
    ...source,
    id: `scale-${i}`,
    name: `Empresa ${i}`,
    latitude: -8.05 + (i % 40) * 0.002,
    longitude: -34.9 + Math.floor(i / 40) * 0.002,
  }));
  await page.route("**/api/leads", (route) => route.fulfill({ json: leads }));
  await page.reload();
  await expect(page.locator(".opportunity-row")).toHaveCount(60);
  await page.getByRole("button", {name:"Ver mapa",exact:true}).click();
  await expect(page.locator(".map-shell")).toHaveAttribute(
    "data-ready",
    "true",
  );
  await expect
    .poll(() => page.locator(".map-cluster").count())
    .toBeGreaterThan(0);
  expect(await page.locator(".map-marker").count()).toBeLessThan(800);
  await page.getByRole("button", { name: /Mostrar mais/ }).click();
  await expect(page.locator(".opportunity-row")).toHaveCount(120);
  await noOverflow(page);
});

test("preferences: English and Spanish, currency and persisted crimson identity", async ({
  page,
}) => {
  const original = (
    (await (await page.request.get("/api/auth/me")).json()) as { user: User }
  ).user;
  try {
    await globalPage(page, "Configurações");
    await choose(page, "Idioma", "English (US)");
    await choose(page, "Default currency", /USD/);
    await page
      .getByRole("button", { name: "Save preferences", exact: true })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: "Preferences saved" }),
    ).toBeVisible();
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "en-US");
    await expect(page.locator("html")).toHaveAttribute("data-currency", "USD");
    await expect(
      page.getByRole("button", { name: "Operate", exact: true }),
    ).toBeVisible();
    await choose(page, "Language", "Español");
    await page
      .getByRole("button", { name: "Guardar preferencias", exact: true })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: "Preferencias guardadas" }),
    ).toBeVisible();
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "es");
    await expect(page.locator("html")).toHaveAttribute(
      "data-accent",
      "crimson",
    );
    await accessible(page);
  } finally {
    await writeApi<User>(
      page,
      "/settings",
      {
        name: original.name,
        timezone: original.timezone,
        locale: original.locale,
        default_currency: original.default_currency,
        accent: original.accent,
        motion: original.motion,
      },
      "PUT",
    );
  }
});

test("research context: explicit actions, enrichment, deep audit and error recovery", async ({
  page,
}) => {
  const lead = await testLead(page, "Pesquisa");
  const research: LeadResearch = {
    id: "research-fixture",
    lead_id: lead.id,
    status: "confirmed",
    provider: "test-fixture",
    website_url: "https://example.com",
    website_status: "poor",
    confidence: 90,
    evidence: [{ key: "name_match" }, { key: "city_match" }],
    checks: [{ key: "https", state: "pass" }],
    sources: [
      { url: "https://example.com", title: "Fonte de teste", kind: "website" },
    ],
    page: { domain: "example.com", title: "Site de teste" },
    audit_level: "none",
    audit: {},
    audited_at: null,
    search_configured: true,
    candidates_checked: 1,
    fetch_errors: 0,
    checked_at: 1790500000,
  };
  const audit: LeadAudit = {
    level: "deep",
    quality_score: 62,
    website_status: "poor",
    pages_checked: 2,
    categories: { technical: { score: 20, max: 25 } },
    findings: [
      {
        key: "no_description",
        severity: "medium",
        label: "Meta description fraca ou ausente",
      },
    ],
    angles: [],
    pages: [{ url: "https://example.com" }],
    signals: {},
  };
  let researchPosts = 0;
  await page.route(`**/api/leads/${lead.id}/research`, (route) => {
    if (route.request().method() === "GET")
      return route.fulfill({ json: { research: null } });
    researchPosts++;
    const result: LeadResearchResponse = { lead, research };
    return route.fulfill({ json: result });
  });
  await page.route(`**/api/leads/${lead.id}/research/deep`, (route) =>
    route.fulfill({
      json: {
        lead,
        research: {
          ...research,
          audit_level: "deep",
          audit,
          audited_at: 1790500001,
        },
      } satisfies LeadResearchResponse,
    }),
  );
  await page.route(`**/api/leads/${lead.id}/enrich`, (route) =>
    route.fulfill({
      json: {
        lead,
        research,
        enrichment: { coverage: 75, missing: ["email"] },
      } satisfies LeadEnrichmentResponse,
    }),
  );
  await page.route(`**/api/leads/${lead.id}/reanalysis`, (route) =>
    route.fulfill({
      json: {
        lead,
        research,
        actions: ["web_research"],
        status: "improved",
        before_confidence: 20,
        after_confidence: 55,
      } satisfies LeadReanalysisResponse,
    }),
  );
  await page.reload();
  await page.getByLabel("Filtrar estabelecimentos encontrados").fill(lead.name);
  await page
    .getByRole("button", { name: `Abrir ${lead.name}`, exact: true })
    .click();
  expect(researchPosts).toBe(0);
  await page.getByRole("tab", { name: "Pesquisa", exact: true }).click();
  await page
    .getByRole("button", { name: "Analisar oportunidade", exact: true })
    .click();
  await expect(
    page.getByText("Site confirmado", { exact: true }),
  ).toBeVisible();
  expect(researchPosts).toBe(1);
  await page
    .getByRole("button", { name: "Auditoria profunda", exact: true })
    .click();
  await expect(page.locator(".deep-audit-score")).toHaveText("62/100");
  await accessible(page);
  await page.screenshot({ path: `${output}/research-audit.png` });
  await page
    .getByRole("button", { name: "Enriquecer dados", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Cobertura dos contatos" }),
  ).toContainText("75%");
  await page
    .getByRole("button", { name: "Aprofundar análise", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Confiança atualizada" }),
  ).toContainText("20 → 55");
  await page.unroute(`**/api/leads/${lead.id}/research`);
  await page.route(`**/api/leads/${lead.id}/research`, (route) =>
    route.fulfill({ status: 503, json: { detail: "Provedor indisponível" } }),
  );
  await page
    .getByRole("button", { name: "Pesquisar novamente", exact: true })
    .click();
  await expect(page.locator(".research-error")).toContainText(
    "Provedor indisponível",
  );
});

test("authentication: responsive forms, password visibility and invalid login", async ({
  page,
  context,
}) => {
  await context.clearCookies();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Entrar", exact: true }),
  ).toBeVisible();
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await noOverflow(page);
    await accessible(page);
  }
  await page.getByLabel("E-mail", { exact: true }).fill("invalid@example.test");
  await page.getByLabel("Senha", { exact: true }).fill("invalid-test-password");
  await page
    .getByRole("button", { name: "Mostrar senha", exact: true })
    .click();
  await expect(page.getByLabel("Senha", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  await page
    .getByRole("button", { name: "Entrar", exact: true })
    .click();
  await expect(page.locator(".error-text")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: `${output}/login-mobile.png`, fullPage: true });
  await page
    .getByRole("button", { name: "Esqueci a senha", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Recuperar senha", exact: true }),
  ).toBeVisible();
  await noOverflow(page);
  await accessible(page);
  await page
    .getByRole("button", { name: "Voltar para entrar", exact: true })
    .click();
  await page.getByRole("button", { name: "Criar conta", exact: true }).click();
  await expect(
    page.getByLabel("Confirmar senha", { exact: true }),
  ).toHaveAttribute("minlength", "12");
  await noOverflow(page);
  await accessible(page);
});
