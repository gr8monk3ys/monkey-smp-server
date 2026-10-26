// The only place the site's links live (prices are in the pages). After changing one, run
// `python tools/site_links.py`: it writes the links into the HTML too, for crawlers and link previews, and
// validate.py fails until you do. Empty string = that button points at the Discord and says "soon".
window.REALMS = {
  ADDRESS: "monkeysmp.lscaturchio.xyz",
  DISCORD_INVITE: "https://discord.gg/C25hy9Ca9W",
  // Tebex webstore (passes and supporter tiers). Fill it in only once the store can take payments and run
  // its commands on the server (docs/LIVE.md, "The store"). While it is empty, the pages say passes are
  // arranged in the Discord (data-store="soon"); once it is set, they say what the store does ("open").
  STORE_URL: "",
  // The player modpack. The GitHub releases are private, so until the Modrinth project is up the site serves
  // the release's own .mrpack and player zip from site/pack/ (docs/MAINTAINING.md, Releasing).
  MODPACK_URL: "pack/TheRealms-Client-2.5.0.mrpack",
  // The player zip: the installer for the regular Minecraft Launcher on Windows, plus the same .mrpack.
  INSTALLER_URL: "pack/TheRealms-Player-2.5.0.zip",
  // Live map (BlueMap behind Caddy on the VPS, docs/LIVE.md), open to everyone.
  MAP_URL: "https://map.monkeysmp.lscaturchio.xyz",
};
