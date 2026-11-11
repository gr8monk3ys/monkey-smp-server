// /changes/feed.xml: the player changelog as RSS, built once into out/ with the rest of the site (src/lib/feed.ts).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CHANGES, feedEntries, rss } from "@/lib/feed";

export const dynamic = "force-static";

export function GET() {
  const mdx = readFileSync(join(process.cwd(), "src", "content", "changes.mdx"), "utf8");
  return new Response(rss(feedEntries(mdx), CHANGES), {
    headers: { "content-type": "application/rss+xml; charset=utf-8" },
  });
}
