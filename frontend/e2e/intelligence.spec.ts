import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

import { spawn } from "node:child_process";
import path from "node:path";

async function semanticAttempt(key: string) {
  const root = path.resolve("..");
  const python =
    process.env.E2E_PYTHON ||
    path.resolve(root, "../../../.venv/Scripts/python.exe");
  return new Promise<{
    status: string;
    model: string;
    reserved_tokens: number;
    actual_tokens: number;
  }>((resolve, reject) => {
    const child = spawn(
      python,
      ["tests/intelligence_browser_fixture.py", "attempt", key],
      { cwd: root, windowsHide: true },
    );
    let output = "",
      error = "";
    child.stdout.on("data", (b) => (output += b));
    child.stderr.on("data", (b) => (error += b));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) reject(new Error(error));
      else {
        try {
          resolve(JSON.parse(output));
        } catch (e) {
          reject(e);
        }
      }
    });
  });
}

test("configured semantic policy reserves budget; saved criteria stay editable; invalid output falls back", async ({
  page,
}) => {
  const login = await page.request.post("/api/auth/login", {
    data: {
      email: "e2e@example.test",
      password: "E2e-only-not-for-production!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const headers = {
    "X-CSRF-Token": (await login.json()).csrf,
    Origin: process.env.E2E_ORIGIN || "http://localhost:8097",
  };
  await page.goto("/#radar");
  await page
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
  await expect(
    dialog.getByRole("combobox", { name: "Interpretação", exact: true }),
  ).toHaveCount(0);
  await dialog
    .getByLabel("O que buscar (opcional)")
    .fill("Consultórios dentários que precisam renovar o site");
  await dialog.getByRole("combobox", { name: "Onde?" }).fill("Recife");
  await dialog.getByRole("listbox").getByRole("option").click();
  const launched = page.waitForResponse(
    (r) =>
      r.url().endsWith("/smart-searches/launch") &&
      r.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "Buscar empresas", exact: true })
    .click();
  const response = await launched;
  const result = await response.json();
  expect(result.status).toBe("started");
  expect(result.job.intent.requirements).toContain("poor_site");
  expect(result.job.intent.location.id).toBe("qa_recife");
  const reservation = await semanticAttempt(
    response.request().postDataJSON().request_key,
  );
  expect(reservation).toMatchObject({
    status: "completed",
    model: "controlled-browser-model",
    actual_tokens: 600,
  });
  expect(reservation.reserved_tokens).toBeGreaterThan(600);
  const progress = page.getByRole("region", { name: "Busca em andamento" });
  await progress.getByRole("button", { name: "Cancelar busca" }).click();
  const name = "QA semântica " + Date.now();
  const saved = await (
    await page.request.post(`/api/smart-searches/${result.job.id}/save`, {
      headers,
      data: { name },
    })
  ).json();
  try {
    await page.reload();
    await page
      .getByRole("button", { name: "Buscas salvas", exact: true })
      .click();
    await page
      .getByRole("dialog", { name: "Buscas salvas" })
      .getByRole("button", { name: new RegExp(`^${name}`) })
      .click();
    await dialog
      .getByRole("button", { name: "Ajustar critérios", exact: true })
      .click();
    const required = dialog.getByRole("group", {
      name: "Requisitos obrigatórios",
      exact: true,
    });
    await expect(
      required.getByRole("checkbox", {
        name: "Site com problemas",
        exact: true,
      }),
    ).toBeChecked();
    await required
      .getByRole("checkbox", { name: "Telefone disponível", exact: true })
      .check();
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      const sizes = await dialog.evaluate((e) => ({
        scroll: e.scrollWidth,
        width: e.clientWidth,
      }));
      expect(sizes.scroll).toBeLessThanOrEqual(sizes.width + 1);
      if (width === 390)
        await page.screenshot({ path: "../artifacts/intelligence-mobile.png" });
    }
    expect(
      (
        await new AxeBuilder({ page })
          .include(".unified-search")
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.screenshot({ path: "../artifacts/intelligence-desktop.png" });
    await page.keyboard.press("Escape");
    await page
      .getByRole("button", { name: "Buscar empresas", exact: true })
      .click();
    await dialog
      .getByLabel("O que buscar (opcional)")
      .fill("Consultórios dentários FALHA CONTROLADA");
    const before = await (await page.request.get("/api/smart-searches")).json();
    const failure = page.waitForResponse(
      (r) =>
        r.url().endsWith("/smart-searches/launch") &&
        r.request().method() === "POST",
    );
    await dialog
      .getByRole("button", { name: "Buscar empresas", exact: true })
      .click();
    const failed = await failure;
    const fallback = await failed.json();
    expect(fallback.status).toBe("clarification");
    expect(fallback.interpretation.mode).toBe("deterministic");
    expect(fallback.interpretation.reason).toContain("inválida");
    await expect(dialog.getByRole("alert")).toContainText(
      "Setor não reconhecido",
    );
    const failedAttempt = await semanticAttempt(
      failed.request().postDataJSON().request_key,
    );
    expect(failedAttempt.status).toBe("fallback");
    expect(failedAttempt.reserved_tokens).toBeGreaterThan(0);
    expect(
      (await (await page.request.get("/api/smart-searches")).json()).length,
    ).toBe(before.length);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  } finally {
    expect(
      (
        await page.request.delete(`/api/radar/saved-searches/${saved.id}`, {
          headers,
        })
      ).ok(),
    ).toBeTruthy();
  }
});

test("observed contacts and contextual evidence persist in the existing lead", async ({
  page,
}) => {
  const login = await page.request.post("/api/auth/login", {
    data: {
      email: "e2e@example.test",
      password: "E2e-only-not-for-production!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const csrf = (await login.json()).csrf;
  const headers = {
    "X-CSRF-Token": csrf,
    Origin: process.env.E2E_ORIGIN || "http://localhost:8010",
  };
  const name = `Contexto P02 QA ${Date.now()}`;
  const created = await page.request.post("/api/leads", {
    headers,
    data: {
      name,
      category: "Oficina",
      city: "Recife",
      country: "BR",
      latitude: -8.05,
      longitude: -34.9,
      website: "https://example.org",
      website_status: "unknown",
      phone: "5581999999999",
    },
  });
  expect(created.status()).toBe(201);
  const lead = await created.json();
  expect(
    (
      await page.request.patch(`/api/leads/${lead.id}/stage`, {
        headers,
        data: { version: lead.version, stage: "discovered" },
      })
    ).ok(),
  ).toBeTruthy();
  await page.goto("/#pipeline");
  await page.getByText(name, { exact: true }).first().click();
  await page.getByRole("tab", { name: "Pesquisa", exact: true }).click();
  await page
    .getByRole("button", { name: "Analisar oportunidade", exact: true })
    .click();
  await page.getByText("Contatos observados no site", { exact: true }).click();
  await expect(
    page.getByText("business@example.org", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Links públicos observados; não representam autorização de contato.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByText("Links de serviços ou cardápio", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("context_services", { exact: true })).toHaveCount(
    0,
  );
  const workflow = await page.request
    .get(`/api/leads/${lead.id}/workflow`)
    .then((r) => r.json());
  expect(
    workflow.evidence.some(
      (e: { observation_key: string; classification: string }) =>
        e.observation_key === "context_services" &&
        e.classification === "probable",
    ),
  ).toBeTruthy();
  await page.reload();
  await page.getByText(name, { exact: true }).first().click();
  await page.getByRole("tab", { name: "Pesquisa", exact: true }).click();
  await page.getByText("Contatos observados no site", { exact: true }).click();
  await expect(
    page.getByText("business@example.org", { exact: false }),
  ).toBeVisible();
  await page.screenshot({ path: "../artifacts/intelligence-contacts.png" });
});
