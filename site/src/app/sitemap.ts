import type { MetadataRoute } from "next";
import { pages } from "@/content/guide/pages";
import { siteUrl as url } from "@/lib/seo";

// Built once into out/sitemap.xml: every page of the site, the guide's in reading order. tools/site_links.py
// --built fails when a built page is missing from it.
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: url("/"), changeFrequency: "weekly", priority: 1 },
    ...pages.map((page) => ({
      url: url(page.href), changeFrequency: "monthly" as const, priority: page.href === "/guide" ? 0.8 : 0.6,
    })),
    { url: url("/changes"), changeFrequency: "weekly", priority: 0.5 },
    { url: url("/creators"), changeFrequency: "monthly", priority: 0.4 },
  ];
}
