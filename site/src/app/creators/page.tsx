import type { Metadata } from "next";
import { Canopy, Footer } from "@/components/chrome";
import { ConfigLink, Store } from "@/components/links";
import { Place } from "@/components/place";
import { terms } from "@/content/rules";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Media rank and creator codes for streamers and YouTubers · Monkey SMP",
  description: "Stream or post videos from Monkey SMP, a free economy lifesteal SMP, and get a free Media rank. "
    + "Regular creators get a code: 10% off for viewers and a share of the sale. The terms.",
  path: "/creators",
});

export default function Creators() {
  return (
    <>
      <Canopy />

      <main id="main">
        <section className="hero">
          <h1>Make videos on Monkey SMP.</h1>
          <p className="lede">Post a video or stream from the server that passes a set view count and you get a free
            Media rank. Creators who play here regularly can also have a creator code: viewers get 10% off the
            cosmetic store, and you get a share of what they paid. The thresholds are public, so you know where you
            stand before you post.</p>
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
          <h2>Getting the rank or a code</h2>
          <p className="note">Open a ticket in the Discord, or <ConfigLink to="CONTACT_URL">contact us</ConfigLink>,
            with a link to the video or stream. For a code, add the code you&apos;d like (your channel name works).
            We&apos;ll set it up and tell you when it works. To be paid, set up a Tebex Wallet when Tebex asks you
            to.</p>
          <Store when="soon">
            <p className="note">The store isn&apos;t open yet, so no code pays out until it opens.</p>
          </Store>
          <div className="cta">
            <ConfigLink to="DISCORD_INVITE" className="button">Join the Discord</ConfigLink>
            <a className="button ghost" href="/#kit">Logo and banners</a>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}
