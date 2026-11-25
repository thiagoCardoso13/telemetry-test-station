/**
 * The whole chain through a real browser: button, web API, ingest, UDP, simulator, and back as
 * telemetry, command status and alarms. Needs the station running (docker compose up).
 */
import { expect, test, type Page } from "@playwright/test";

const tile = (page: Page, name: string) => page.locator(".tile", { hasText: name });
const button = (page: Page, name: string) => page.getByRole("button", { name, exact: true });
const alarm = (page: Page, text: string) => page.locator(".banner", { hasText: text });
const latestCommand = (page: Page) =>
  page.locator("section", { has: page.getByRole("heading", { name: "Recent commands" }) })
    .getByRole("listitem")
    .first();

const valveRow = (page: Page, name: string) => page.locator(".row", { hasText: name });

async function pressure(page: Page): Promise<number> {
  return Number.parseFloat(await tile(page, "tank pressure").locator("strong").innerText());
}

async function openValve(page: Page, name: "Fill valve" | "Vent valve") {
  await valveRow(page, name).getByRole("button", { name: "Open" }).click();
}

async function inject(page: Page, fault: string, option: { magnitude?: string; valve?: string }) {
  await page.getByLabel("Fault").selectOption({ label: fault });
  if (option.valve) {
    await page.getByLabel("valve that stays as it is").selectOption({ label: option.valve });
  }
  if (option.magnitude) {
    await page.getByLabel("rate per second, up to 1").fill(option.magnitude);
  }
  await button(page, "Inject").click();
  await expect(latestCommand(page)).toContainText("completed");
}

async function reset(page: Page) {
  await button(page, "Reset tank").click();
  await expect(latestCommand(page)).toContainText("reset — completed");
  await expect(tile(page, "fill valve")).toContainText("Closed");
  await expect(page.locator(".banner")).toHaveCount(0);
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toContainText("Live");
  await reset(page);
});

test.afterEach(async ({ page }) => {
  await reset(page);
});

test("a command reaches the tank and shows up in the telemetry", async ({ page }) => {
  await expect.poll(() => pressure(page)).toBeCloseTo(2, 1);

  await openValve(page, "Fill valve");

  await expect(latestCommand(page)).toContainText("open fill valve — completed");
  await expect(tile(page, "fill valve")).toContainText("Open");
  await expect.poll(() => pressure(page)).toBeGreaterThan(4);
});

test("a stuck relief valve ends in a high pressure alarm", async ({ page }) => {
  await inject(page, "Stuck valve", { valve: "relief" });
  await openValve(page, "Fill valve");

  await expect(alarm(page, "tank pressure above the limit")).toBeVisible();
  expect(await pressure(page)).toBeGreaterThan(8);

  await reset(page);
  await expect(page.getByText("✓ cleared: tank pressure high").first()).toBeVisible();
});

test("a leak ends in a low pressure alarm", async ({ page }) => {
  await inject(page, "Leak", { magnitude: "0.8" });

  await expect(alarm(page, "tank pressure below the limit")).toBeVisible();
});

test("a stuck valve is reported to the operator", async ({ page }) => {
  await inject(page, "Stuck valve", { valve: "vent" });

  await openValve(page, "Vent valve");

  await expect(latestCommand(page)).toContainText("open vent valve — failed: valve is stuck");
  await expect(tile(page, "vent valve")).toContainText("Closed");
});
