import { test, expect } from "@playwright/test";

test("visible map area and drawn polygon use the unified worker launch and saved intent", async ({
  page,
}) => {
  test.setTimeout(90000);
  const login = await page.request.post("/api/auth/login", {
    data: {
      email: "e2e@example.test",
      password: "E2e-only-not-for-production!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const headers = {
    "X-CSRF-Token": (await login.json()).csrf,
    Origin: process.env.E2E_ORIGIN || "http://localhost:8077",
  };
  await page.goto("/#radar");
  await page
    .getByRole("textbox", {
      name: "Filtrar estabelecimentos encontrados",
      exact: true,
    })
    .fill("Café do Pátio");
  await page.getByRole("button", { name: "Ver mapa", exact: true }).click();
  await expect(page.locator(".map-shell")).toHaveAttribute(
    "data-ready",
    "true",
  );
  let legacyCalls = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/radar/search")
    )
      legacyCalls++;
  });
  for (const kind of ["bounds", "polygon"] as const) {
    if (kind === "polygon") {
      await page
        .getByRole("textbox", {
          name: "Filtrar estabelecimentos encontrados",
          exact: true,
        })
        .fill("Café do Pátio");
      await page
        .getByRole("button", { name: "Centralizar oportunidades", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Desenhar território", exact: true })
        .click();
      const canvas = page.locator(".maplibregl-canvas");
      const box = await canvas.boundingBox();
      expect(box).toBeTruthy();
      for (const [x, y] of [
        [0.32, 0.35],
        [0.65, 0.35],
        [0.32, 0.65],
      ]) {
        await canvas.click({
          position: { x: box!.width * x, y: box!.height * y },
        });
      }
      await page
        .getByRole("button", { name: "Concluir área", exact: true })
        .click();
    }
    await page
      .getByRole("button", {
        name:
          kind === "bounds"
            ? /Buscar nesta área visível/
            : /Buscar no território/,
      })
      .click();
    const dialog = page.getByRole("dialog", { name: "Buscar empresas" });
    await expect(dialog.locator("input,select,textarea")).toHaveCount(3);
    await expect(dialog.getByLabel("Onde?", { exact: true })).toHaveValue(
      kind === "bounds" ? "Área visível do mapa" : "Território desenhado",
    );
    await expect(dialog.getByLabel("Onde?", { exact: true })).toHaveAttribute(
      "readonly",
      "",
    );
    await dialog.getByLabel("O que buscar (opcional)").fill("Hamburguerias");
    const launched = page.waitForResponse(
      (r) =>
        r.url().endsWith("/smart-searches/launch") &&
        r.request().method() === "POST",
    );
    await dialog
      .getByRole("button", { name: "Buscar empresas", exact: true })
      .click();
    const response = await launched;
    expect(response.ok()).toBeTruthy();
    const job = (await response.json()).job;
    expect(job.intent.area.kind).toBe(kind);
    expect(job.intent.area.bounds).toHaveLength(4);
    expect(job.intent.market.city).toBe("");
    expect(job.intent.market.country).toBe("");
    expect(job.status).toBe("pending");
    await expect(dialog).toHaveCount(0);
    const progress = page.getByRole("region", { name: "Busca em andamento" });
    await progress.getByRole("button", { name: "Cancelar busca" }).click();
    if (kind === "polygon") {
      await progress
        .getByRole("button", { name: "Salvar busca", exact: true })
        .click();
      const name = `QA território ${Date.now()}`;
      await progress.getByLabel("Nome da busca").fill(name);
      await progress
        .getByRole("button", { name: "Salvar", exact: true })
        .click();
      await expect(
        progress.getByRole("button", { name: "Busca salva", exact: true }),
      ).toBeDisabled();
      const saved = (
        await (await page.request.get("/api/radar/saved-searches")).json()
      ).find((row: { name: string }) => row.name === name);
      try {
        await page.reload();
        await page
          .getByRole("button", { name: "Buscas salvas", exact: true })
          .click();
        await page
          .getByRole("dialog", { name: "Buscas salvas" })
          .getByRole("button", { name: new RegExp(`^${name}`) })
          .click();
        await expect(dialog.getByLabel("Onde?", { exact: true })).toHaveValue(
          "Território desenhado",
        );
        expect(saved.query.commercial_intent.area).toEqual(job.intent.area);
        await page.screenshot({ path: "../artifacts/v137/map-search.png" });
        await page.keyboard.press("Escape");
      } finally {
        expect(
          (
            await page.request.delete(`/api/radar/saved-searches/${saved.id}`, {
              headers,
            })
          ).ok(),
        ).toBeTruthy();
      }
    } else {
      await progress
        .getByRole("button", { name: "Voltar ao Radar completo" })
        .click();
    }
  }
  expect(legacyCalls).toBe(0);
});
