import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { preload } from "react-dom";
import { Motion } from "@/components/motion";
import { SITE_URL } from "@/lib/config";
import "./tailwind.css";
import "./style.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "Monkey SMP",
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
  // The display face and the body face, before the stylesheet asks for them (style.css's @font-face).
  for (const font of ["pixelify-sans-monkey-bold", "atkinson-next-latin"]) {
    preload(`/fonts/${font}.woff2`, { as: "font", type: "font/woff2", crossOrigin: "" });
  }
  return (
    <html lang="en">
      <body>
        <Motion>{children}</Motion>
      </body>
    </html>
  );
}
