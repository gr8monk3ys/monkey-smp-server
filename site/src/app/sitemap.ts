import type { MetadataRoute } from "next";
import { pages } from "@/content/guide/pages";
import { SITE_URL } from "@/lib/config";

// Built once into out/sitemap.xml: every page of the site, the guide's in reading order.
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const url = (path: string) => `${SITE_URL}${path === "/" ? "/" : path}`;
  return [
    { url: url("/"), changeFrequency: "weekly", priority: 1 },
    ...pages.map((page) => ({
      url: url(page.href), changeFrequency: "monthly" as const, priority: page.href === "/guide" ? 0.8 : 0.6,
    })),
    { url: url("/changes"), changeFrequency: "weekly", priority: 0.5 },
    { url: url("/creators"), changeFrequency: "monthly", priority: 0.4 },
  ];
}
