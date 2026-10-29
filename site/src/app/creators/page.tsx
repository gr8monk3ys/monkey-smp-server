import type { Metadata } from "next";
import { Canopy, Footer } from "@/components/chrome";
import { ConfigLink, Store } from "@/components/links";
import { Place } from "@/components/place";
import { terms } from "@/content/rules";

export const metadata: Metadata = {
  title: "Creator codes · Monkey SMP",
  description: "Stream or post videos from Monkey SMP and earn a share of the passes your viewers buy. The terms for "
    + "creator codes.",
  openGraph: {
    title: "Creator codes · Monkey SMP",
    description: "Stream or post videos from Monkey SMP and earn a share of the passes your viewers buy.",
    type: "website",
    url: "/creators",
    images: ["/img/og.jpg"],
  },
};

export default function Creators() {
  return (
    <>
      <Canopy label="Pages" items={[
        { label: "The server", href: "/" },
        { label: "Pricing", href: "/#pricing" },
        { label: "Terms", href: "#terms" },
        { label: "Guide", href: "/guide" },
        { label: "Discord", to: "DISCORD_INVITE" },
      ]} />

      <main id="main">
        <section className="hero">
          <h1>Make videos on Monkey SMP.</h1>
          <p className="lede">If you stream or post videos from the server, you can have a creator code. Viewers who
            enter it when they buy a pass pay the same as everyone else, and you get a share of what they paid. Small
            channels are welcome: the server holds 30 players, so we&apos;d rather have a few creators who play here
            than a big one who visits once.</p>
        </section>

        <section id="terms">
          <h2>The terms</h2>
          <Place as="ol" className="rules terms">
            {terms.map((t) => <li key={t.title}><h3>{t.title}</h3><p>{t.text}</p></li>)}
          </Place>
          <p className="small">Tebex pays creators under its own terms, which may ask you for details before it pays
            out.</p>
        </section>

        <section id="apply">
          <h2>Getting a code</h2>
          <p className="note">Open a ticket in the Discord with a link to your channel and the code you&apos;d like
            (your channel name works). We&apos;ll make it in the store and tell you when it works. To be paid, set up
            a Tebex Wallet when Tebex asks you to.</p>
          <Store when="soon">
            <p className="note">The store isn&apos;t open yet, so no code pays out until it opens. Until then, passes
              are arranged in the Discord.</p>
          </Store>
          <div className="cta">
            <ConfigLink to="DISCORD_INVITE" className="button">Join the Discord</ConfigLink>
            <a className="button ghost" href="/#kit">Logo and banners</a>
          </div>
        </section>
      </main>

      <Footer items={[
        { label: "Monkey SMP", href: "/" },
        { label: "Discord", to: "DISCORD_INVITE" },
        { label: "Rules", href: "/#rules" },
        { label: "Live map", to: "MAP_URL" },
        { label: "How it works", href: "/guide" },
      ]} />
    </>
  );
}
