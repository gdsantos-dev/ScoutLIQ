import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir, writeFile } from "node:fs/promises";

test("experience: navigation, decision record and responsive evidence", async ({
  page,
}) => {
  test.setTimeout(240000);
  const baseline = process.env.EXPERIENCE_BASELINE === "1";
  const folder = `../artifacts/experience/${baseline ? "before" : "after"}`;
  await mkdir(folder, { recursive: true });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("E-mail", { exact: true }).fill("e2e@example.test");
  await page
    .getByLabel("Senha", { exact: true })
    .fill("E2e-only-not-for-production!");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page.locator(".radar-results")).toBeVisible();
  if (baseline)
    await page.getByRole("button", { name: "Ver lista", exact: true }).click();
  const measurements = [];
  for (const width of [320, 375, 390, 430, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByTestId("page-view")).toHaveCSS("opacity", "1");
    await page.evaluate(() =>
      Promise.all(
        document
          .getAnimations()
          .filter((a) => a.effect?.getTiming().iterations !== Infinity)
          .map((a) => a.finished.catch(() => {})),
      ),
    );
    const dimensions = await page.evaluate(() => ({
      width: innerWidth,
      actual: document.documentElement.scrollWidth,
    }));
    expect(dimensions.actual).toBeLessThanOrEqual(width + 1);
    measurements.push(dimensions);
    await page.screenshot({
      path: `${folder}/radar-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("button", { name: "Abrir Café do Pátio", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.screenshot({ path: `${folder}/record-desktop.png` });
  if (!baseline) {
    await page
      .getByRole("button", { name: "Abrir ficha operacional", exact: true })
      .click();
    await expect(
      page.getByRole("group", { name: "Trabalho da oportunidade" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Abordagem", exact: true }).click();
    await expect(page.locator("#workflow-outreach")).toBeVisible();
    await expect(page.locator("#workflow-evidence")).toBeHidden();
    await page
      .getByRole("button", { name: "Revisão humana", exact: true })
      .click();
    await expect(page.locator("#workflow-review")).toBeVisible();
    await page.getByRole("button", { name: "Evidências", exact: true }).click();
    await expect(page.locator("#workflow-evidence")).toBeVisible();
    const audit = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    await writeFile(
      `${folder}/axe-record.json`,
      JSON.stringify(audit.violations, null, 2),
    );
    expect(audit.violations).toEqual([]);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: `${folder}/record-mobile.png` });
  await page
    .getByRole("button", { name: "Fechar detalhes", exact: true })
    .click();
  if (!baseline) {
    const toggle = page.locator(
      'button[aria-controls="workspace-destinations"]',
    );
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await page
      .getByRole("navigation", { name: "Navegação principal" })
      .getByRole("button", { name: "Oportunidades", exact: true })
      .click();
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await page
      .getByRole("button", { name: "Gerir clientes", exact: true })
      .click();
    await toggle.click();
    await page
      .getByRole("navigation", { name: "Navegação principal" })
      .getByRole("button", { name: "Clientes", exact: true })
      .click();
    await expect(page.locator("#main-content h1")).toHaveText("Clientes");
    await page.getByRole("button", { name: "Operar", exact: true }).click();
    await expect(page.locator("#main-content h1")).toHaveText("Oportunidades");
    const audit = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    await writeFile(
      `${folder}/axe-mobile.json`,
      JSON.stringify(audit.violations, null, 2),
    );
    expect(audit.violations).toEqual([]);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute(
      "data-motion",
      "reduced",
    );
  }
  await writeFile(
    `${folder}/viewports.json`,
    JSON.stringify({ measurements, errors }, null, 2),
  );
  expect(errors).toEqual([]);
});

test("radar: context survives navigation and the map loads only on demand", async ({
  page,
}) => {
  const login = await page.request.post("/api/auth/login", {
    data: {
      email: "e2e@example.test",
      password: "E2e-only-not-for-production!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const started = Date.now();
  await page.goto("/#radar");
  const filter = page.getByRole("textbox", {
    name: "Filtrar estabelecimentos encontrados",
    exact: true,
  });
  await expect(filter).toBeVisible();
  await expect(page.locator(".map-shell")).toHaveCount(0);
  const initial = await page.evaluate(() =>
    performance.getEntriesByType("resource").map((e) => e.name),
  );
  expect(initial.some((url) => /OpportunityMap-.*\.js/.test(url))).toBeFalsy();
  const readyMs = Date.now() - started;
  await filter.fill("Café do Pátio");
  await expect(
    page.getByRole("button", { name: "Abrir Café do Pátio", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("navigation", { name: "Navegação principal" })
    .getByRole("button", { name: "Campanhas", exact: true })
    .click();
  await expect(page.locator("#main-content h1")).toHaveText("Campanhas");
  await page
    .getByRole("navigation", { name: "Navegação principal" })
    .getByRole("button", { name: "Radar", exact: true })
    .click();
  await expect(filter).toHaveValue("Café do Pátio");
  await page.getByRole("button", { name: "Ver mapa", exact: true }).click();
  await expect(page.locator(".map-shell")).toBeVisible();
  await expect(page.locator(".map-shell")).toHaveAttribute(
    "data-ready",
    "true",
  );
  await page.screenshot({
    path: "../artifacts/experience/after/radar-map-desktop.png",
  });
  const requested = await page.evaluate(() =>
    performance
      .getEntriesByType("resource")
      .map((e) => ({
        url: e.name,
        duration: e.duration,
        bytes: (e as PerformanceResourceTiming).transferSize,
      })),
  );
  expect(
    requested.some((e) => /OpportunityMap-.*\.js/.test(e.url)),
  ).toBeTruthy();
  await writeFile(
    "../artifacts/experience/performance.json",
    JSON.stringify(
      {
        scope:
          "One local Chromium run; synthetic preview data, no external provider latency",
        readyMs,
        initialResourceCount: initial.length,
        mapDeferred: true,
        resources: requested,
      },
      null,
      2,
    ),
  );
});

test("new search entry points follow English and Spanish preferences", async ({
  page,
}) => {
  const login = await page.request.post("/api/auth/login", {
    data: {
      email: "e2e@example.test",
      password: "E2e-only-not-for-production!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const session = await page.request.get("/api/auth/me").then((r) => r.json());
  const original = session.user;
  await page.goto("/#radar");
  const headers = {
    "X-CSRF-Token": session.csrf,
    Origin: new URL(page.url()).origin,
  };
  const settings = {
    name: original.name,
    timezone: original.timezone,
    locale: original.locale,
    default_currency: original.default_currency,
    accent: original.accent,
    motion: original.motion,
  };
  try {
    for (const [locale, search, label, where, adjust] of [
      [
        "en-US",
        "Find businesses",
        "What to find (optional)",
        "Where?",
        "Adjust criteria",
      ],
      ["es", "Buscar empresas", "Qué buscar (opcional)", "¿Dónde?", "Ajustar criterios"],
    ]) {
      expect(
        (
          await page.request.put("/api/settings", {
            headers,
            data: { ...settings, locale },
          })
        ).ok(),
      ).toBeTruthy();
      await page.reload();
      await page.getByRole("button", { name: search, exact: true }).click();
      const dialog = page.getByRole("dialog", { name: search, exact: true });
      await expect(dialog.getByLabel(label, { exact: true })).toBeVisible();
      await expect(
        dialog.getByRole("combobox", { name: where, exact: true }),
      ).toBeVisible();
      await expect(dialog.locator("input,select,textarea")).toHaveCount(3);
      await dialog.getByRole("combobox", { name: where, exact: true }).fill("falha");
      await expect(dialog.getByRole("alert")).toHaveText(locale === "en-US" ? "Locations unavailable. Try again; no area was selected." : "Ubicaciones no disponibles. Inténtalo de nuevo; no se seleccionó ningún área.");
      await expect(
        dialog.getByRole("button", { name: adjust, exact: true }),
      ).toBeVisible();
      await expect(
        dialog.getByRole("button", { name: search, exact: true }),
      ).toBeDisabled();
      await dialog.getByRole("button", { name: adjust, exact: true }).click();
      const niches = dialog.getByRole("group", { name: locale === "en-US" ? "Optional niches (up to 4)" : "Nichos opcionales (hasta 4)" });
      await expect(niches).toBeVisible();
      expect(await niches.getByRole("checkbox", { checked: true }).count()).toBe(0);
      await expect(dialog.getByLabel(label, { exact: true })).toHaveValue("");
      await page.screenshot({ path: `../artifacts/v1381/criteria-${locale}.png` });
      await page.keyboard.press("Escape");
    }
  } finally {
    expect(
      (
        await page.request.put("/api/settings", { headers, data: settings })
      ).ok(),
    ).toBeTruthy();
  }
});
