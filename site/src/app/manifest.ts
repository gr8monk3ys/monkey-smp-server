import type { MetadataRoute } from "next";

// Built once into out/manifest.webmanifest: the name, colours and icons a phone uses for the site on its home
// screen. The colours are DESIGN.md's ground and canopy leaf.
export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Monkey SMP",
    short_name: "Monkey SMP",
    description: "A modded Minecraft Java factions server: the address, the pack, the rules and the guide.",
    start_url: "/",
    display: "browser",
    background_color: "#133f2b",
    theme_color: "#1f6142",
    icons: [
      { src: "/favicon.svg", type: "image/svg+xml", sizes: "any" },
      { src: "/img/icon-256.png", type: "image/png", sizes: "256x256" },
      { src: "/kit/mark-512.png", type: "image/png", sizes: "512x512" },
    ],
  };
}
