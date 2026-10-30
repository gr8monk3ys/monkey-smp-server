import type { Metadata } from "next";
import { Canopy, Footer } from "@/components/chrome";
import { ConfigLink } from "@/components/links";

// Every address the site doesn't have (out/404.html): the site's own page, with the ways back, rather than
// Next's default, which is drawn for a white page and can't be read on this one. Next marks it noindex itself.
export const metadata: Metadata = {
  title: { absolute: "Page not found · Monkey SMP" },
};

export default function NotFound() {
  return (
    <>
      <Canopy label="Site" items={[
        { label: "Join", href: "/#join" },
        { label: "Rules", href: "/#rules" },
        { label: "Guide", href: "/guide" },
        { label: "Discord", to: "DISCORD_INVITE" },
      ]} />

      <main id="main">
        <section className="hero lost">
          <h1>Nothing here.</h1>
          <p className="lede">This page doesn&apos;t exist, or it has moved. The server&apos;s address, the pass and
            the modpack are on the front page, how things work is in the guide, and anything else you can ask in
            the <ConfigLink to="DISCORD_INVITE">Discord</ConfigLink>.</p>
          <div className="ways">
            <div className="cta">
              <a className="button" href="/">Go to the front page</a>
              <a className="button ghost" href="/guide">Read the guide</a>
            </div>
          </div>
        </section>
      </main>

      <Footer items={[
        { label: "Monkey SMP", href: "/" },
        { label: "Discord", to: "DISCORD_INVITE" },
        { label: "Rules", href: "/#rules" },
        { label: "Live map", to: "MAP_URL" },
        { label: "What changed", href: "/changes" },
      ]} />
    </>
  );
}
