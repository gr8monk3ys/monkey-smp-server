// The staff page, built into ../deploy/staff (which Caddy serves from the checkout; the VPS has no Node).
//
// Two builds, each one script and one stylesheet with a fixed name and no shared chunks:
//   app   index.html                          -> app.js, app.css      (behind the session check)
//   auth  login.html, reset.html, verify.html -> auth.js, auth.css    (open: Caddy's @locked list names them)
// `bun run build` runs both. The policy (deploy/Caddyfile.staff-login) allows no inline script or style, so nothing
// here may inline one: no modulepreload polyfill, no inlined assets, and tests/test_staff_ui.py checks the output.
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { readFileSync, writeFileSync } from "node:fs";
import { defineConfig, type Plugin } from "vite";

// STAFF_UI_OUT builds somewhere else: tools/staff_ui_fresh.py builds into a temporary folder and compares.
const OUT = resolve(import.meta.dirname, process.env.STAFF_UI_OUT || "../deploy/staff");

// reset.html and verify.html are login.html with their own title and data-page: one entry, so the one script keeps
// its name (auth.js), which Caddy's @locked list lets a visitor with no session load.
const AUTH_PAGES = { reset: "New password", verify: "Confirm email" };
function otherAuthPages(): Plugin {
  return {
    name: "monkey-auth-pages",
    closeBundle() {
      const login = readFileSync(resolve(OUT, "login.html"), "utf8");
      for (const [page, title] of Object.entries(AUTH_PAGES)) {
        const html = login
          .replace(/<title>[^<]*<\/title>/, `<title>${title}: Monkey SMP staff</title>`)
          .replace('data-page="login"', `data-page="${page}"`);
        writeFileSync(resolve(OUT, `${page}.html`), html);
      }
    },
  };
}

export default defineConfig(({ mode }) => {
  const auth = mode === "auth";
  const name = auth ? "auth" : "app";
  const pages = auth ? ["login"] : ["index"];
  return {
    plugins: [react(), tailwindcss(), ...(auth ? [otherAuthPages()] : [])],
    // The site's fonts and pictures are served by Caddy at /fonts/ and /img/ (from site/public); left as they are.
    publicDir: false,
    base: "/",
    build: {
      outDir: OUT,
      emptyOutDir: false,        // mod-settings.json lives there too (tools/staff_modcfg.py reads it)
      assetsInlineLimit: 0,
      cssCodeSplit: false,
      modulePreload: { polyfill: false },
      minify: true,
      sourcemap: false,
      reportCompressedSize: false,
      rollupOptions: {
        input: Object.fromEntries(pages.map((p) => [p, resolve(import.meta.dirname, `${p}.html`)])),
        output: {
          entryFileNames: `${name}.js`,
          chunkFileNames: `${name}-[name].js`,
          assetFileNames: (info) => (info.names?.[0]?.endsWith(".css") ? `${name}.css` : "[name][extname]"),
        },
      },
    },
  };
});
