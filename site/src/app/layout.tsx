import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { JsonLd } from "@/components/json-ld";
import { SITE_URL } from "@/lib/config";
import { preloadFont } from "@/lib/fonts";
import { OG_IMAGE, SITE_NAME, siteGraph } from "@/lib/seo";
import "./tailwind.css";
import "./style.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  // Every page sets its own title, description and canonical address (pageMetadata in src/lib/seo.ts); these are
  // what a page that forgets falls back to.
  title: SITE_NAME,
  description: "A modded Minecraft Java factions server with a paid whitelist: factions, territory, PvP and seasons.",
  applicationName: SITE_NAME,
  openGraph: { siteName: SITE_NAME, type: "website", locale: "en_US", images: [OG_IMAGE] },
  twitter: { card: "summary_large_image" },
  icons: {
    icon: { url: "/favicon.svg", type: "image/svg+xml" },
    apple: "/img/icon-256.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#1f6142",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // The display face and the body face, before the stylesheet asks for them (style.css's @font-face). The mono
  // face is preloaded only by the pages that show code (preloadMono).
  preloadFont("pixelify-sans-monkey-bold");
  preloadFont("atkinson-next-latin");
  return (
    <html lang="en">
      <body>
        <JsonLd data={siteGraph()} />
        {children}
      </body>
    </html>
  );
}
