// Every built page, at phone and desktop width (playwright.config.ts): no serious or critical WCAG A/AA problem
// that axe-core can see, one visible h1, and nothing wider than the screen. axe catches about a third of what
// matters for accessibility; this is the guard against regressions, not the whole review.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { SITE_URL } from "../src/lib/config";

/** Every page the sitemap lists (tools/site_links.py --built checks it lists every built page), plus the 404. */
function pages(): string[] {
  const sitemap = readFileSync(join(__dirname, "..", "out", "sitemap.xml"), "utf8");
  const paths = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1].replace(SITE_URL, "") || "/");
  return [...paths, "/no-such-page"];
}

/** The site's own files only: the server status, the standings and the analytics are on other hosts, and each
 * page has a quiet fallback for when they don't answer (src/components/status.tsx, standings.tsx). */
async function offline(page: Page) {
  await page.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => route.abort());
}

for (const path of pages()) {
  test(`${path} reads well`, async ({ page }) => {
    await offline(page);
    await page.goto(path, { waitUntil: "load" });

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(blocking.map((v) => ({ id: v.id, help: v.help, nodes: v.nodes.map((n) => n.target.join(" ")) })))
      .toEqual([]);

    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.locator("h1")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, "the page is wider than the screen").toBeLessThanOrEqual(0);
  });
}

test("a question opens and closes from the keyboard", async ({ page }) => {
  await offline(page);
  await page.goto("/#faq");
  const first = page.locator(".faq details").first();
  await first.locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(first).toHaveAttribute("open", "");
  await expect(first.locator("p")).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(first).not.toHaveAttribute("open", "");
});
