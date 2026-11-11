// The changelog's RSS feed as built: /changes lists it in its head and links it, and each item opens its entry.
import { expect, test } from "@playwright/test";
import { SITE_URL } from "../src/lib/config";

test("the feed is built, listed on /changes, and its items land on their entries", async ({ page, request }) => {
  await page.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => route.abort());
  await page.goto("/changes");
  const listed = page.locator('link[rel="alternate"][type="application/rss+xml"]');
  await expect(listed).toHaveAttribute("href", /\/changes\/feed\.xml$/);
  await expect(page.getByRole("link", { name: /feed reader/ })).toHaveAttribute("href", "/changes/feed.xml");

  const feed = await request.get("/changes/feed.xml");
  expect(feed.ok()).toBe(true);
  const xml = await feed.text();
  expect(xml).toContain('<rss version="2.0"');
  const first = xml.match(/<item><title>[^<]*<\/title><link>([^<]+)<\/link>/)?.[1];
  expect(first).toBeTruthy();
  const anchor = first!.replace(`${SITE_URL}/changes#`, "");
  await expect(page.locator(`article[id="${anchor}"]`)).toHaveCount(1);
});
