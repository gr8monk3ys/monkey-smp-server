// Serves the built site (out/) the way Vercel does with vercel.json's cleanUrls: /guide is out/guide.html,
// / is out/index.html, a file is itself, and anything else is out/404.html with a 404. Only for the browser
// checks (playwright.config.ts starts it); run with `bun e2e/serve.ts [port]`.
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";

const root = resolve(__dirname, "..", "out");
const port = Number(process.argv[2] ?? process.env.PORT ?? 4317);

const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2",
  ".xml": "application/xml", ".txt": "text/plain; charset=utf-8", ".mp4": "video/mp4", ".webm": "video/webm",
  ".webmanifest": "application/manifest+json", ".ics": "text/calendar",
};

async function find(pathname: string): Promise<string | null> {
  const clean = normalize(decodeURIComponent(pathname)).replace(/^[/\\]+/, "");
  if (clean.startsWith("..")) return null;
  const tries = clean === "" || clean === "." ? ["index.html"] : [`${clean}.html`, clean, join(clean, "index.html")];
  for (const name of tries) {
    const path = join(root, name);
    if (await stat(path).then((s) => s.isFile(), () => false)) return path;
  }
  return null;
}

createServer(async (request, response) => {
  const found = await find(new URL(request.url ?? "/", "http://localhost").pathname);
  const path = found ?? join(root, "404.html");
  response.writeHead(found ? 200 : 404, { "content-type": TYPES[extname(path)] ?? "application/octet-stream" });
  createReadStream(path).pipe(response);
}).listen(port, "127.0.0.1", () => console.log(`serving out/ on http://127.0.0.1:${port}`));
