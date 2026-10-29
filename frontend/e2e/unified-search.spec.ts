import { test, expect, type BrowserContext } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { spawn } from "node:child_process";
import path from "node:path";
let requestHeaders: Record<string, string>;
let authState: Awaited<ReturnType<BrowserContext["storageState"]>>;

test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext();
  const origin = process.env.E2E_ORIGIN || "http://localhost:8001";
  const login = await context.request.post(`${origin}/api/auth/login`, {
    data: {
      email: "e2e@example.test",
      password: "E2e-only-not-for-production!",
    },
  });
  expect(login.ok()).toBeTruthy();
  requestHeaders = {
    "X-CSRF-Token": (await login.json()).csrf,
    Origin: origin,
  };
  authState = await context.storageState();
  await context.close();
});

test.beforeEach(async ({ page }) => {
  await page.context().addCookies(authState.cookies);
  await page.goto("/#radar");
  await expect(
    page.getByRole("button", { name: "Buscar empresas", exact: true }),
  ).toBeVisible();
});

test("three fields, catalog errors, keyboard selection, responsive dialog and focus restoration", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
  await expect(dialog.locator("input,textarea,select")).toHaveCount(3);
  await expect(dialog.getByLabel("Quantidade", { exact: true })).toHaveValue(
    "50",
  );
  await dialog.getByLabel("O que buscar (opcional)").fill("Hamburguerias");
  await dialog.getByRole("combobox", { name: "Onde?" }).fill("falha");
  await expect(dialog.getByRole("alert")).toContainText(
    "Localizações indisponíveis",
  );
  await expect(
    dialog.getByRole("button", { name: "Buscar empresas", exact: true }),
  ).toBeDisabled();
  await dialog.getByRole("combobox", { name: "Onde?" }).fill("Recife");
  await expect(dialog.getByRole("listbox").getByRole("option")).toHaveCount(1);
  await dialog.getByRole("combobox", { name: "Onde?" }).press("ArrowDown");
  await dialog.getByRole("combobox", { name: "Onde?" }).press("Enter");
  await expect(
    dialog.getByRole("button", { name: "Buscar empresas", exact: true }),
  ).toBeEnabled();
  for (const target of ["25", "50", "75", "100"]) {
    await dialog.getByLabel("Quantidade", { exact: true }).selectOption(target);
    await expect(dialog.getByLabel("Quantidade", { exact: true })).toHaveValue(
      target,
    );
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 800 });
    const bounds = await dialog.evaluate((e) => ({
      scroll: e.scrollWidth,
      width: e.clientWidth,
      height: e.getBoundingClientRect().height,
      viewport: innerHeight,
      blur: getComputedStyle(e, "::backdrop").backdropFilter,
      ownBlur: getComputedStyle(e).backdropFilter,
      body: document.body.style.position,
    }));
    expect(bounds.scroll).toBeLessThanOrEqual(bounds.width + 1);
    expect(bounds.height).toBeLessThanOrEqual(bounds.viewport);
    expect(bounds.blur).toBe("blur(8px)");
    expect(bounds.ownBlur).toBe("none");
    expect(bounds.body).toBe("fixed");
    if (width === 390)
      await page.screenshot({ path: "../artifacts/v137/search-mobile.png" });
  }
  const audit = await new AxeBuilder({ page })
    .include(".unified-search")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    audit.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
  await page.screenshot({ path: "../artifacts/v137/search-desktop.png" });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Buscar empresas", exact: true }),
  ).toBeFocused();
  expect(await page.evaluate(() => document.body.style.position)).toBe("");
});

test("launch closes modal, existing worker persists results, reload and history restore the same search", async ({
  page,
}) => {
  // These exact records belong to the isolated provider fixture. Other review
  // scenarios intentionally change their qualification; start from fresh facts.
  const fixtureNames = [
    "Clínica QA Aurora",
    "Clínica QA Horizonte",
    "Starbucks QA Centro",
  ];
  const fixtureLeads = (await (
    await page.request.get("/api/leads")
  ).json()) as { id: string; name: string }[];
  for (const lead of fixtureLeads.filter((row) =>
    fixtureNames.includes(row.name),
  )) {
    expect(
      (
        await page.request.delete(`/api/leads/${lead.id}`, {
          headers: requestHeaders,
        })
      ).ok(),
    ).toBeTruthy();
  }
  await page
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
  await dialog.getByLabel("O que buscar (opcional)").fill("Clínicas odontológicas");
  await dialog.getByRole("combobox", { name: "Onde?" }).fill("Recife");
  await dialog.getByRole("listbox").getByRole("option").click();
  await dialog.getByLabel("Quantidade", { exact: true }).selectOption("25");
  await dialog
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: "Busca em andamento" }),
  ).toContainText("Aguardando início");
  const searchId = await page.evaluate(
    () =>
      Object.keys(localStorage)
        .filter((k) => k.endsWith(":active-search"))
        .map((k) => localStorage.getItem(k))[0],
  );
  expect(searchId).toBeTruthy();
  const root = path.resolve("..");
  const python =
    process.env.SCOUT_TEST_PYTHON ||
    path.resolve(root, "../../../.venv/Scripts/python.exe");
  await new Promise<void>((resolve, reject) => {
    const child = spawn(
      python,
      ["tests/unified_browser_fixture.py", "worker"],
      {
        cwd: root,
        windowsHide: true,
        env: { ...process.env, E2E_PORT: new URL(page.url()).port },
      },
    );
    let output = "";
    child.stdout.on("data", (b) => (output += b));
    child.stderr.on("data", (b) => (output += b));
    child.on("error", reject);
    child.on("close", (code) =>
      code === 0 ? resolve() : reject(new Error(output)),
    );
  });
  await page.reload();
  const progress = page.getByRole("region", { name: "Busca em andamento" });
  await expect(progress).toContainText("Resultado parcial");
  await expect(progress).toContainText("2 / 25 qualificadas");
  await expect(
    page.getByRole("button", { name: "Abrir Clínica QA Aurora", exact: true }),
  ).toBeVisible();
  await progress.getByLabel("Exibir resultados").selectOption("discarded");
  await expect(
    page.getByRole("button", {
      name: "Abrir Starbucks QA Centro",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Abrir Clínica QA Aurora", exact: true }),
  ).toHaveCount(0);
  await progress
    .getByRole("button", { name: "Voltar ao Radar completo" })
    .click();
  await page.getByText("Buscas recentes", { exact: true }).click();
  await page
    .locator(".search-history button")
    .filter({ hasText: "Clínicas odontológicas" })
    .first()
    .click();
  await expect(
    page.getByRole("region", { name: "Busca em andamento" }),
  ).toContainText("2 / 25 qualificadas");
  await page.screenshot({
    path: "../artifacts/v137/search-results.png",
    fullPage: true,
  });
});

test("nested record and edit dialogs retain background lock until the last dialog closes", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Abrir Café do Pátio", exact: true })
    .click();
  await expect(page.locator(".context-panel")).toBeVisible();
  await page
    .getByRole("button", { name: "Editar empresa", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(2);
  expect(await page.evaluate(() => document.body.style.position)).toBe("fixed");
  await page.keyboard.press("Escape");
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  expect(await page.evaluate(() => document.body.style.position)).toBe("fixed");
  await page.keyboard.press("Escape");
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  expect(await page.evaluate(() => document.body.style.position)).toBe("");
});

test("commercial review is persisted in the record with required evidence", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Abrir Café do Pátio", exact: true })
    .click();
  await page.getByRole("tab", { name: "Análise", exact: true }).click();
  const review = page.getByRole("region", { name: "Revisão comercial" });
  await review
    .getByRole("button", { name: "Revisar dados comerciais" })
    .click();
  await review.getByLabel("Operação", { exact: true }).selectOption("active");
  await review
    .getByLabel("Autonomia", { exact: true })
    .selectOption("independent");
  await expect(
    review.getByRole("button", { name: "Registrar revisão" }),
  ).toBeDisabled();
  await review
    .getByLabel("Evidência e motivo")
    .fill("Revisão sintética de QA: autonomia e operação verificadas.");
  await review.getByRole("button", { name: "Registrar revisão" }).click();
  await expect(review.getByRole("status")).toHaveText("Revisão registrada.");
  await page.reload();
  await page
    .getByRole("button", { name: "Abrir Café do Pátio", exact: true })
    .click();
  await page.getByRole("tab", { name: "Análise", exact: true }).click();
  await expect(review).toContainText(
    "Revisão sintética de QA: autonomia e operação verificadas.",
  );
  await expect(review).toContainText(
    "Independente / autonomia local verificada",
  );
  const confirmation = page.waitForResponse(r => r.url().endsWith("/review") && r.request().method() === "POST");
  await review.getByRole("button", { name: "Confirmar avaliação atual", exact: true }).click();
  const confirmed = await confirmation;
  expect(confirmed.ok()).toBeTruthy();
  expect(confirmed.request().postDataJSON().confirm_existing).toBe(true);
  expect((await confirmed.json()).qualification.review_reason).toBe("Revisão sintética de QA: autonomia e operação verificadas.");
  await expect(review.getByRole("status")).toHaveText("Revisão registrada.");
});

test("optional criteria require acknowledgement before dropping unsupported text", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
  await dialog
    .getByLabel("O que buscar (opcional)")
    .fill("Hamburguerias com mais de 200 avaliações");
  await dialog.getByRole("combobox", { name: "Onde?" }).fill("Recife");
  await dialog.getByRole("listbox").getByRole("option").click();
  await dialog
    .getByRole("button", { name: "Ajustar critérios", exact: true })
    .click();
  const criteria = dialog.getByRole("region", { name: "Ajustar critérios" });
  await expect(criteria).toContainText("Limites numéricos");
  await criteria
    .getByRole("group", { name: "Requisitos obrigatórios" })
    .getByLabel("WhatsApp disponível")
    .check();
  await dialog
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  await expect(dialog.getByRole("alert")).toContainText("Limites numéricos");
  await criteria
    .getByLabel(
      "Aplicar somente os critérios acima; ignorar os trechos não reconhecidos.",
    )
    .check();
  await page.setViewportSize({ width: 390, height: 700 });
  const size = await dialog.evaluate((e) => ({
    scroll: e.scrollWidth,
    width: e.clientWidth,
    height: e.getBoundingClientRect().height,
  }));
  expect(size.scroll).toBeLessThanOrEqual(size.width + 1);
  expect(size.height).toBeLessThanOrEqual(700);
  const checkbox = await criteria.getByRole("checkbox").first().boundingBox();
  expect(checkbox?.width).toBe(18);
  expect(checkbox?.height).toBe(18);
  await page.screenshot({ path: "../artifacts/v137/criteria-mobile.png" });
  await dialog
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  const progress = page.getByRole("region", { name: "Busca em andamento" });
  await progress.getByRole("button", { name: "Cancelar busca" }).click();
  await expect(progress).toContainText("Cancelada");
});

test("saved search reopens the unified form without losing reviewed criteria or geography", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
  await dialog.getByLabel("O que buscar (opcional)").fill("Hamburguerias");
  await dialog.getByRole("combobox", { name: "Onde?" }).fill("Recife");
  await dialog.getByRole("listbox").getByRole("option").click();
  await dialog.getByLabel("Quantidade", { exact: true }).selectOption("75");
  await dialog
    .getByRole("button", { name: "Ajustar critérios", exact: true })
    .click();
  const criteria = dialog.getByRole("region", { name: "Ajustar critérios" });
  await criteria
    .getByRole("group", { name: "Requisitos obrigatórios" })
    .getByLabel("WhatsApp disponível")
    .check();
  await criteria
    .getByRole("group", { name: "Preferências", exact: true })
    .getByLabel("Instagram disponível")
    .check();
  await dialog
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  const progress = page.getByRole("region", { name: "Busca em andamento" });
  await progress.getByRole("button", { name: "Cancelar busca" }).click();
  await progress
    .getByRole("button", { name: "Salvar busca", exact: true })
    .click();
  const name = `QA critérios preservados ${Date.now()}`;
  await progress.getByLabel("Nome da busca").fill(name);
  await progress.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(
    progress.getByRole("button", { name: "Busca salva", exact: true }),
  ).toBeDisabled();
  await page.reload();
  const savedRows = await (
    await page.request.get("/api/radar/saved-searches")
  ).json();
  const saved = savedRows.find((row: { name: string }) => row.name === name);
  expect(saved.query.commercial_intent.requirements).toContain("whatsapp");
  expect(saved.query.commercial_intent.preferences).toContain("instagram");
  try {
    await page
      .getByRole("button", { name: "Buscas salvas", exact: true })
      .click();
    await page
      .getByRole("dialog", { name: "Buscas salvas" })
      .getByRole("button", { name: new RegExp(`^${name}`) })
      .click();
    await expect(page.locator("dialog[open]")).toHaveCount(1);
    await expect(dialog.getByLabel("O que buscar (opcional)")).toHaveValue(
      "Hamburguerias",
    );
    await expect(dialog.getByLabel("Quantidade", { exact: true })).toHaveValue(
      "75",
    );
    await expect(dialog.getByRole("combobox", { name: "Onde?" })).toHaveValue(
      "Recife, Pernambuco, Brasil",
    );
    await dialog
      .getByRole("button", { name: "Ajustar critérios", exact: true })
      .click();
    await expect(
      criteria
        .getByRole("group", { name: "Requisitos obrigatórios" })
        .getByLabel("WhatsApp disponível"),
    ).toBeChecked();
    await expect(
      criteria
        .getByRole("group", { name: "Preferências", exact: true })
        .getByLabel("Instagram disponível"),
    ).toBeChecked();
    const launched = page.waitForResponse(
      (r) =>
        r.url().endsWith("/smart-searches/launch") &&
        r.request().method() === "POST",
    );
    await dialog
      .getByRole("button", { name: "Buscar empresas", exact: true })
      .click();
    const next = (await (await launched).json()).job;
    for (const key of [
      "sectors",
      "requirements",
      "preferences",
      "exclusions",
      "profile",
      "requirement_mode",
      "target",
    ]) {
      expect(next.intent[key]).toEqual(saved.query.commercial_intent[key]);
    }
    expect(next.intent.location.id).toBe(
      saved.query.commercial_intent.location.id,
    );
    await progress.getByRole("button", { name: "Cancelar busca" }).click();
  } finally {
    const removed = await page.request.delete(
      `/api/radar/saved-searches/${saved.id}`,
      { headers: requestHeaders },
    );
    expect(removed.ok()).toBeTruthy();
  }
});

test("natural command opens the same search form and restores dialog ownership", async ({
  page,
}) => {
  await page.keyboard.press("Control+k");
  await page
    .getByRole("combobox", { name: "Buscar empresas ou comandos" })
    .fill("Hamburguerias em Recife");
  await page
    .getByRole("option", {
      name: /Pesquisar no Radar: Hamburguerias em Recife/,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
  await expect(dialog.getByLabel("O que buscar (opcional)")).toHaveValue(
    "Hamburguerias em Recife",
  );
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  expect(await page.evaluate(() => document.body.style.position)).toBe("fixed");
  await page.keyboard.press("Escape");
  expect(await page.evaluate(() => document.body.style.position)).toBe("");
});

test("opportunities use the same search form and return results to Radar", async ({
  page,
}) => {
  await page.goto("/#opportunities");
  await page
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
  await dialog.getByLabel("O que buscar (opcional)").fill("Hamburguerias");
  await dialog.getByRole("combobox", { name: "Onde?" }).fill("Recife");
  await dialog.getByRole("listbox").getByRole("option").click();
  await dialog
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  await expect(page).toHaveURL(/#radar$/);
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  const progress = page.getByRole("region", { name: "Busca em andamento" });
  await expect(progress).toContainText("Hamburguerias");
  await progress.getByRole("button", { name: "Cancelar busca" }).click();
});

test("saved legacy intent requires a catalog selection instead of reusing another remembered city", async ({
  page,
}) => {
  const interpreted = await page.request.post("/api/smart-searches/prepare", {
    headers: requestHeaders,
    data: { text: "Clínicas odontológicas em Recife, Brasil", target: 25 },
  });
  expect(interpreted.ok()).toBeTruthy();
  const intent = (await interpreted.json()).intent;
  const name = `QA intenção antiga ${Date.now()}`;
  const response = await page.request.post("/api/radar/saved-searches", {
    headers: requestHeaders,
    data: {
      name,
      query: {
        location: "Recife",
        country: "BR",
        category: "dentista",
        commercial_intent: intent,
      },
    },
  });
  expect(response.status()).toBe(201);
  const saved = await response.json();
  try {
    await page.reload();
    const userId = (await (await page.request.get("/api/auth/me")).json()).user
      .id;
    await page.evaluate((id) => {
      localStorage.setItem(
        `scoutliq-radar-last-search:${id}:search-location`,
        JSON.stringify({
          place: {
            id: "wrong-city",
            name: "Olinda",
            formatted: "Olinda, Pernambuco, Brasil",
            administrative_type: "city",
            country: "Brasil",
            country_code: "BR",
          },
          query: "Olinda",
        }),
      );
    }, userId);
    await page
      .getByRole("button", { name: "Buscas salvas", exact: true })
      .click();
    await page
      .getByRole("dialog", { name: "Buscas salvas" })
      .getByRole("button", { name: new RegExp(`^${name}`) })
      .click();
    const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
    await expect(dialog.getByRole("combobox", { name: "Onde?" })).toHaveValue(
      /recife/i,
    );
    await expect(
      dialog.getByRole("button", { name: "Buscar empresas", exact: true }),
    ).toBeDisabled();
    await dialog.getByRole("listbox").getByRole("option").click();
    await expect(
      dialog.getByRole("button", { name: "Buscar empresas", exact: true }),
    ).toBeEnabled();
    await page.keyboard.press("Escape");
  } finally {
    expect(
      (
        await page.request.delete(`/api/radar/saved-searches/${saved.id}`, {
          headers: requestHeaders,
        })
      ).ok(),
    ).toBeTruthy();
  }
});
