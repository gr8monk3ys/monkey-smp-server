# The Realms site

The public page at therealmsmc.lscaturchio.xyz: what the server is, how to join, pricing and the rules.
Plain HTML and CSS, no build step. Links and the server address live in `config.js`; prices and rules are
in `index.html`.

Deploy: a Vercel project on this repo with **Root Directory** `site` and framework preset **Other**, with the
domain `therealmsmc.lscaturchio.xyz` added to it. The Minecraft address uses the SRV record in
docs/LIVE.md, so the website and the game share the name.

Preview locally: `python -m http.server -d site 8000`.
