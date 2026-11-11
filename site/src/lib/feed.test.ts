// Run with `bun test`. The changelog's RSS feed (src/lib/feed.ts), from a small changes.mdx and the real one.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { config, SITE_URL } from "./config";
import { bodyHtml, CHANGES, entryId, feedEntries, rss } from "./feed";

const SAMPLE = `{/* A comment with <Entry date="2000-01-01" title="Not real"> in it. */}

<Entry label="Next update" title="Not out yet">

- Nothing dated.

</Entry>

<Entry date="2026-11-10" title="Drawers & copper">

- Storage Drawers is in the modpack. Press <kbd>M</kbd> for the map,
  then \`/trigger wardrobe\`.
- The map moved: <ConfigLink to="MAP_URL">the live map</ConfigLink>. See [the guide](/guide).
- **Update the modpack.**

</Entry>`;

test("only dated entries go in the feed, with an id from their date and title", () => {
  const entries = feedEntries(SAMPLE);
  assert.equal(entries.length, 1);
  assert.equal(entries[0].id, "2026-11-10-drawers-and-copper");
  assert.equal(entryId(undefined, "Not out yet"), "next-not-out-yet");
});

test("a body becomes one list, with code, keys, bold and links resolved", () => {
  const html = feedEntries(SAMPLE)[0].html;
  assert.ok(html.startsWith("<ul><li>") && html.endsWith("</li></ul>"));
  assert.equal(html.match(/<li>/g)?.length, 3);
  assert.match(html, /<kbd>M<\/kbd> for the map, then <code>\/trigger wardrobe<\/code>/);
  assert.match(html, new RegExp(`<a href="${config.MAP_URL}">the live map</a>`));
  assert.match(html, new RegExp(`<a href="${SITE_URL}/guide">the guide</a>`));
  assert.match(html, /<strong>Update the modpack.<\/strong>/);
});

test("anything else that looks like HTML is escaped", () => {
  assert.equal(bodyHtml("- a <script> & b"), "<ul><li>a &lt;script&gt; &amp; b</li></ul>");
  assert.equal(bodyHtml("A paragraph."), "<p>A paragraph.</p>");
});

test("the feed is RSS with each item linking to its entry on /changes", () => {
  const xml = rss(feedEntries(SAMPLE), CHANGES);
  assert.match(xml, /^<\?xml version="1.0" encoding="UTF-8"\?>/);
  assert.match(xml, /<title>Drawers &amp; copper<\/title>/);
  assert.match(xml, new RegExp(`<link>${SITE_URL}/changes#2026-11-10-drawers-and-copper</link>`));
  assert.match(xml, /<pubDate>Tue, 10 Nov 2026 20:00:00 GMT<\/pubDate>/);
  assert.ok(!xml.includes("<li>"), "item bodies are escaped inside <description>");
});

test("the real changelog makes a feed with unique ids and no markdown left over", () => {
  const mdx = readFileSync(join(__dirname, "..", "content", "changes.mdx"), "utf8");
  const entries = feedEntries(mdx);
  assert.ok(entries.length > 5);
  assert.equal(new Set(entries.map((e) => e.id)).size, entries.length);
  for (const e of entries) {
    assert.ok(!/\*\*|<ConfigLink|\]\(/.test(e.html), `${e.id} still has markdown or JSX: ${e.html}`);
  }
});
