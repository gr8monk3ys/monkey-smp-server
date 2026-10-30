import { preload } from "react-dom";

/** Asks for one of public/fonts/ before the stylesheet does (style.css's @font-face), so text first paints in it. */
export function preloadFont(name: string) {
  preload(`/fonts/${name}.woff2`, { as: "font", type: "font/woff2", crossOrigin: "" });
}

/** The mono face, for a page that shows <code> (the front page's address, the guide's commands, the changelog):
 * a page without code doesn't fetch it at all. */
export const preloadMono = () => preloadFont("atkinson-mono-latin");
