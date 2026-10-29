import type { Metadata } from "next";
import { Fragment } from "react";
import { Canopy, Footer } from "@/components/chrome";
import { Place } from "@/components/place";
import { type Command, ranks, roles } from "@/content/guide/commands";
import Factions from "@/content/guide/factions.mdx";
import FirstHour from "@/content/guide/first-hour.mdx";
import { week } from "@/content/guide/week";
import WeekNotes from "@/content/guide/week-notes.mdx";
import "./guide.css";

export const metadata: Metadata = {
  title: "How it works - Monkey SMP",
  description: "How Monkey SMP works: the first hour, factions and land, a week of challenges, drops and events, "
    + "and every command by rank, from player to admin.",
};

function Term({ cmd }: { cmd: Command }) {
  if ("code" in cmd) return <code>{cmd.code}</code>;
  if ("kbd" in cmd) return <kbd>{cmd.kbd}</kbd>;
  return <>{cmd.term}</>;
}

function Commands({ cmds }: { cmds: Command[] }) {
  return (
    <dl className="cmds">
      {cmds.map((cmd, i) => <div key={i}><dt><Term cmd={cmd} /></dt><dd>{cmd.does}</dd></div>)}
    </dl>
  );
}

export default function Guide() {
  return (
    <>
      <Canopy label="Site" items={[
        { label: "Join", href: "/#join" },
        { label: "Rules", href: "/#rules" },
        { label: "The week", href: "#week" },
        { label: "Commands", href: "#commands" },
      ]} />

      <main id="main">
        <section className="hero">
          <h1>How the server works</h1>
          <p className="lede">What happens when you join, how factions and land work, what a week brings, and every
            command you can type, by rank. New here? Read the first two parts. The rest is for when you need it.</p>
          <nav className="toc" aria-label="On this page">
            <p><b>The server</b><a href="#first-hour">Your first hour</a><a href="#factions">Factions and land</a><a
              href="#week">A week on the server</a></p>
            <p><b>Commands by rank</b>{roles.map((r) => <a key={r.id} href={`#${r.id}`}>{r.title}</a>)}</p>
          </nav>
        </section>

        <section id="first-hour">
          <div className="prose"><FirstHour /></div>
        </section>

        <section id="factions">
          <div className="prose"><Factions /></div>
        </section>

        <section id="week">
          <h2>A week on the server</h2>
          <p className="note">The same rhythm every week of the season. Times are Pacific.</p>
          <Place as="ol" className="week">
            {week.map((day) => (
              <li key={day.name} className={day.place}>
                <h3>{day.name}</h3>
                {day.lines.map((line, i) => (
                  <p key={i} className={line.quiet ? "quiet" : undefined}>
                    {line.at && <span className="at">{line.at}</span>}{line.text}
                  </p>
                ))}
              </li>
            ))}
          </Place>
          <p className="small">The Town Crier at spawn has the next two Saturday events.</p>
          <div className="prose"><WeekNotes /></div>
        </section>

        <section id="commands">
          <h2>Commands by rank</h2>
          <p className="note">Each rank can do everything the ranks above it can. Supporters and faction leaders are
            players with a few extras, not staff.</p>
          <dl className="ranks">
            {ranks.map((rank) => (
              <div key={rank.name}>
                <dt>{rank.id ? <a href={`#${rank.id}`}>{rank.name}</a> : rank.name}</dt>
                <dd>{rank.does}</dd>
              </div>
            ))}
          </dl>

          {roles.map((role) => (
            <div className="role" id={role.id} key={role.id}>
              <h3>{role.title}</h3>
              <p>{role.intro}</p>
              {role.groups.map((group, i) => (
                <Fragment key={i}>
                  {group.heading && <h4>{group.heading}</h4>}
                  {group.note && <p className="small">{group.note}</p>}
                  {group.text && <p>{group.text}</p>}
                  {group.cmds && <Commands cmds={group.cmds} />}
                </Fragment>
              ))}
              {role.after && <p className="small">{role.after}</p>}
            </div>
          ))}
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
