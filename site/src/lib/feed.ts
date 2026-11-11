// The player changelog as an RSS feed (/changes/feed.xml, src/app/changes/feed.xml/route.ts), read straight from
// src/content/changes.mdx when the site is built. Only dated entries go in: "Next update" isn't out yet.
import { config, type LinkKey, target, SITE_URL } from "@/lib/config";

export type FeedEntry = { date: string; title: string; id: string; html: string };

/** What /changes and its feed are called and say they are (one copy for the page's metadata and the feed). */
export const CHANGES = {
  title: "What changed: Monkey SMP patch notes",
  description: "Monkey SMP's patch notes: every change to the server's rules, mods, modpack and wardrobe that "
    + "players notice, newest first.",
  feed: "/changes/feed.xml",
};

/** The id an entry's article carries on /changes, so a feed item links straight to it: its date and title. */
export function entryId(date: string | undefined, title: string): string {
  const words = title.toLowerCase().replace(/&/g, " and ").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return date ? `${date}-${words}` : `next-${words}`;
}

const escape = (text: string) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");

const absolute = (href: string) => (href.startsWith("/") ? `${SITE_URL}${href}` : href);

/** One line of the changelog's markdown as HTML: `code`, **bold**, [links](...), <kbd> and <ConfigLink>. */
function inline(text: string): string {
  const linked = text.replace(/<ConfigLink to="(\w+)">([\s\S]*?)<\/ConfigLink>/g,
    (_, key: string, words: string) => (key in config ? `[${words}](${target(key as LinkKey).href})` : words));
  return escape(linked)
    .replace(/&lt;(\/?)kbd&gt;/g, "<$1kbd>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, words: string, href: string) => `<a href="${absolute(href)}">${words}</a>`);
}

/** An entry's body (a markdown list, now and then a paragraph) as HTML. */
export function bodyHtml(body: string): string {
  const blocks: { list: boolean; text: string }[] = [];
  let open: { list: boolean; text: string } | null = null;
  for (const line of body.split(/\r?\n/)) {
    if (!line.trim()) {
      open = null;
      continue;
    }
    if (/^\s*- /.test(line)) {
      open = { list: true, text: line.replace(/^\s*- /, "") };
      blocks.push(open);
    } else if (open) {
      open.text += ` ${line.trim()}`;
    } else {
      open = { list: false, text: line.trim() };
      blocks.push(open);
    }
  }
  let html = "";
  for (const [i, block] of blocks.entries()) {
    const startsList = block.list && !blocks[i - 1]?.list;
    const endsList = block.list && !blocks[i + 1]?.list;
    html += (startsList ? "<ul>" : "") + (block.list ? `<li>${inline(block.text)}</li>` : `<p>${inline(block.text)}</p>`)
      + (endsList ? "</ul>" : "");
  }
  return html;
}

/** The dated entries of changes.mdx, newest first as the file has them. */
export function feedEntries(mdx: string): FeedEntry[] {
  const source = mdx.replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
  const entries: FeedEntry[] = [];
  for (const match of source.matchAll(/<Entry\s([^>]*)>([\s\S]*?)<\/Entry>/g)) {
    const attrs = Object.fromEntries([...match[1].matchAll(/(\w+)="([^"]*)"/g)].map((m) => [m[1], m[2]]));
    if (!attrs.date || !attrs.title) continue;
    entries.push({ date: attrs.date, title: attrs.title, id: entryId(attrs.date, attrs.title), html: bodyHtml(match[2]) });
  }
  return entries;
}

/** The feed itself: RSS 2.0, each item's body as escaped HTML, dated at noon Pacific on its day. */
export function rss(entries: FeedEntry[], { title, description }: { title: string; description: string }): string {
  const page = `${SITE_URL}/changes`;
  const items = entries.map((e) => [
    "<item>",
    `<title>${escape(e.title)}</title>`,
    `<link>${page}#${e.id}</link>`,
    `<guid isPermaLink="true">${page}#${e.id}</guid>`,
    `<pubDate>${new Date(`${e.date}T12:00:00-08:00`).toUTCString()}</pubDate>`,
    `<description>${escape(e.html)}</description>`,
    "</item>",
  ].join(""));
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
    `<title>${escape(title)}</title>`,
    `<link>${page}</link>`,
    `<atom:link href="${page}/feed.xml" rel="self" type="application/rss+xml"/>`,
    `<description>${escape(description)}</description>`,
    "<language>en-us</language>",
    ...(entries[0] ? [`<lastBuildDate>${new Date(`${entries[0].date}T12:00:00-08:00`).toUTCString()}</lastBuildDate>`] : []),
    ...items,
    "</channel></rss>",
    "",
  ].join("\n");
}
