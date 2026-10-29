import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { spawn } from "node:child_process";
import path from "node:path";

const origin = process.env.E2E_ORIGIN || "http://localhost:8004";
async function prepare(page: Page) {
  const login = await page.request.post("/api/auth/login", {
    data: {
      email: "e2e@example.test",
      password: "E2e-only-not-for-production!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const headers = { "X-CSRF-Token": (await login.json()).csrf, Origin: origin };
  const interpretation = await page.request.post(
    "/api/smart-searches/interpret",
    {
      headers,
      data: { text: "Clínicas odontológicas em Recife, Brasil", target: 25 },
    },
  );
  const intent = (await interpretation.json()).intent;
  const response = await page.request.post("/api/radar/saved-searches", {
    headers,
    data: {
      name: "Autonomia QA " + Date.now(),
      query: {
        location: "Recife",
        country: "BR",
        category: "dentista",
        commercial_intent: intent,
      },
    },
  });
  expect(response.status()).toBe(201);
  return { saved: await response.json(), headers };
}

test("routine configuration, history, mobile, keyboard and error recovery", async ({
  page,
}) => {
  const { saved, headers } = await prepare(page);
  try {
    await page.goto("/#automations");
    const row = page.getByRole("article", { name: saved.name });
    await row.getByRole("button", { name: "Configurar rotina" }).click();
    await page.getByLabel("Tarefas por execução", { exact: true }).fill("8");
    await page.getByLabel("Limite total de execuções").fill("2");
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 950 });
      const size = await page
        .locator("dialog[open]")
        .evaluate((e) => ({ scroll: e.scrollWidth, width: e.clientWidth }));
      expect(size.scroll).toBeLessThanOrEqual(size.width + 1);
      if (width === 390)
        await page.screenshot({ path: "../artifacts/autonomy-mobile.png" });
    }
    const audit = await new AxeBuilder({ page })
      .include(".routine-config")
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      audit.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => n.target),
      })),
    ).toEqual([]);
    await page.screenshot({ path: "../artifacts/autonomy-config.png" });
    await page.getByRole("button", { name: "Salvar pausada" }).click();
    await expect(row).toContainText("Pausada");
    await row.getByRole("button", { name: "Histórico da rotina" }).click();
    await page
      .getByText("Critérios e limites registrados", { exact: true })
      .click();
    await expect(
      page
        .locator(".routine-history-data tr")
        .filter({ hasText: "Tarefas por execução" }),
    ).toContainText("8");
    await page.keyboard.press("Escape");
    await expect(page.locator("dialog[open]")).toHaveCount(0);
    await row.getByRole("button", { name: "Retomar rotina" }).click();
    await expect(row).toContainText("Ativa");
    await row.getByRole("button", { name: "Pausar rotina" }).click();
    await expect(row).toContainText("Pausada");
    await page.route("**/api/operations/routines", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Executor indisponível no teste." }),
      }),
    );
    await page.getByRole("button", { name: "Atualizar rotinas" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "Executor indisponível",
    );
    await page.unroute("**/api/operations/routines");
    await page.getByRole("button", { name: "Atualizar rotinas" }).click();
    await expect(page.getByRole("alert")).toHaveCount(0);
  } finally {
    await page.request.delete("/api/radar/saved-searches/" + saved.id, {
      headers,
    });
  }
});

test("scheduled routine finishes with browser closed using continuous worker", async ({
  page,
  context,
}) => {
  test.setTimeout(90000);
  const { saved, headers } = await prepare(page);
  let child: ReturnType<typeof spawn> | undefined;
  try {
    // The commercial-review scenario intentionally changes one of these fixtures.
    // Reset only this controlled source's companies so independent reruns start alike.
    const existing = (await page.request
      .get("/api/leads")
      .then((r) => r.json())) as { id: string; name: string }[];
    for (const lead of existing.filter((l) =>
      [
        "Clínica QA Aurora",
        "Clínica QA Horizonte",
        "Starbucks QA Centro",
      ].includes(l.name),
    )) {
      const removed = await page.request.delete("/api/leads/" + lead.id, {
        headers,
      });
      expect(removed.ok()).toBeTruthy();
    }
    await page.goto("/#automations");
    const row = page.getByRole("article", { name: saved.name });
    await row.getByRole("button", { name: "Configurar rotina" }).click();
    await page.getByLabel("Limite total de execuções").fill("1");
    await page.getByRole("button", { name: "Ativar rotina" }).click();
    await expect(row).toContainText("Ativa");
    await row.getByRole("button", { name: "Agendar agora" }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "Execução agendada." }),
    ).toBeVisible();
    await page.close();
    child = spawn(
      process.env.E2E_PYTHON || "python",
      ["tests/autonomy_browser_worker.py"],
      { cwd: path.resolve(".."), windowsHide: true, stdio: "pipe" },
    );
    let output = "";
    child.stderr?.on("data", (data) => (output += data.toString()));
    await expect
      .poll(
        async () => {
          if (child?.exitCode !== null) throw new Error(output);
          const rows = await context.request
            .get("/api/operations/routines")
            .then((r) => r.json());
          return rows.find((r: { id: string }) => r.id === saved.id)?.state;
        },
        { timeout: 60000, intervals: [1000] },
      )
      .toBe("completed");
    const rows = await context.request
      .get("/api/operations/routines")
      .then((r) => r.json());
    const completed = rows.find((r: { id: string }) => r.id === saved.id);
    expect(completed.runs).toHaveLength(1);
    expect(completed.runs[0].usage.tasks).toBeGreaterThan(0);
    expect(completed.runs[0].usage.tasks).toBeLessThanOrEqual(20);
    expect(completed.runs[0].result.qualified).toBe(2);
    expect(completed.runs[0].result.discarded).toBe(1);
    const reopened = await context.newPage();
    await reopened.goto("/#automations");
    const resultRow = reopened.getByRole("article", { name: saved.name });
    await resultRow
      .getByText("Execuções recentes (1)", { exact: true })
      .click();
    await expect(resultRow).toContainText("2 qualificadas");
    await reopened.screenshot({ path: "../artifacts/autonomy-result.png" });
    await resultRow.getByRole("button", { name: "Ver resultados" }).click();
    await expect(reopened).toHaveURL(/#radar$/);
    await expect(
      reopened.getByRole("region", { name: "Busca em andamento" }),
    ).toContainText("Resultado parcial");
    await expect(
      reopened.getByRole("region", { name: "Busca em andamento" }),
    ).toContainText("2 / 25 qualificadas");
    await expect(reopened.locator("dialog[open]")).toHaveCount(0);
  } finally {
    if (child && child.exitCode === null) {
      child.kill();
      await new Promise<void>((resolve) =>
        child!.once("exit", () => resolve()),
      );
    }
    await context.request.delete("/api/radar/saved-searches/" + saved.id, {
      headers,
    });
  }
});
