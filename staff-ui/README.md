# staff-ui: the staff page's source

The staff page (`staff.<domain>`, docs/LIVE.md, "The staff page") is a React 19 app built with Vite and Tailwind 4,
in the site's look (DESIGN.md, "Staff page"). The VPS has no Node, so the build is committed: `bun run build` writes
`deploy/staff/`, and Caddy serves that folder from the checkout. `tools/checks.py` (and CI) fails when
`deploy/staff/` is not the build of this folder (`tools/staff_ui_fresh.py`).

```bash
cd staff-ui
bun install --frozen-lockfile
bun run build        # deploy/staff/: index.html, app.js, app.css, login.html, reset.html, verify.html, auth.js, auth.css
bun run lint
bun run typecheck
```

Change something here, run `bun run build`, and commit `deploy/staff/` with it. `STAFF_UI_OUT=<folder>` builds
somewhere else (the freshness check uses it). `deploy/staff/mod-settings.json` is not built: `tools/staff_modcfg.py`
reads it and the page fetches it.

## Two builds

- **The panel** (`index.html`, `src/main.tsx`): `/app.js` and `/app.css`, behind Caddy's `forward_auth`.
- **The login pages** (`login.html`, `src/auth/`): `/auth.js` and `/auth.css`, which Caddy serves without a
  session. `reset.html` and `verify.html` are `login.html` with their own `data-page` and title, made by the build.

File names are fixed (no hashes): Caddy's open list names them, and the browser asks the server each time anyway.

## Under the policy

Caddy sends `script-src 'self'; style-src 'self'; img-src 'self' data:`: no inline script or style. So:

- Every look is a class. Nothing sets a `style` attribute, nothing adds a `<style>` element at run time, and no
  library that does (Radix, framer-motion, most chart and toast libraries) comes in. Charts are SVG with classes.
- Text only: nothing from the server goes in as HTML (no `dangerouslySetInnerHTML`, no `innerHTML`).
- Every request carries `X-Monkey-Staff: 1`. Only `src/lib/api.ts` (the panel), `src/lib/auth.ts` (the login) and
  `src/lib/status.tsx` (`staff.json`) call `fetch`.

`tests/test_staff_ui.py` checks the built bundles and the source for all of this; `tests/test_staff_*.py` check
each tab's source for what it must send and show.

## Layout

- `src/shell/`: the frame (rail on a desktop, a sideways row of tabs on a phone), the header with the status word,
  and the account menu. `tabs.ts` lists the tabs, their group and the role each needs.
- `src/tabs/<tab>/`: one folder per tab. A tab stays mounted once opened and gets `active`; tabs talk through
  `src/lib/bus.ts` (open a file, run a command, the players or the files changed).
- `src/ui/kit.tsx`: the building blocks (panels, buttons, fields, messages, the confirm box). Build from these.
- `src/styles/`: the tokens (the site's colours, faces and pixel frames) and the components' classes.

The fonts and the monkey come from the public site (`/fonts/`, `/img/`), which Caddy serves to the staff page too.
