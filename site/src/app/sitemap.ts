import type { MetadataRoute } from "next";
import { allPages } from "@/content/guide/pages";
import { siteUrl as url } from "@/lib/seo";

// Built once into out/sitemap.xml: every page of the site, the guide's in reading order (a page the sidebar
// leaves out while its pack isn't running too: it still builds). tools/site_links.py
// --built fails when a built page is missing from it.
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: url("/"), changeFrequency: "weekly", priority: 1 },
    ...allPages.map((page) => ({
      url: url(page.href), changeFrequency: "monthly" as const, priority: page.href === "/guide" ? 0.8 : 0.6,
    })),
    { url: url("/changes"), changeFrequency: "weekly", priority: 0.5 },
    { url: url("/creators"), changeFrequency: "monthly", priority: 0.4 },
    { url: url("/privacy"), changeFrequency: "yearly", priority: 0.2 },
    { url: url("/terms"), changeFrequency: "yearly", priority: 0.2 },
  ];
}
