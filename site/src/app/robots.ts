import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/config";

// Built once into out/robots.txt: every page may be crawled; the sitemap lists them.
export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
