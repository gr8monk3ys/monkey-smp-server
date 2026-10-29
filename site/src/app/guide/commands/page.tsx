import { guideMetadata, GuidePage } from "@/components/guide-page";
import { ranks } from "@/content/guide/commands";

export const metadata = guideMetadata("/guide/commands");

export default function Ranks() {
  return (
    <GuidePage href="/guide/commands" lede="Each rank can do everything the ranks above it can. Supporters and faction
      leaders are players with a few extras, not staff.">
      <dl className="ranks">
        {ranks.map((rank) => (
          <div key={rank.name}>
            <dt>{rank.id ? <a href={`/guide/commands/${rank.id}`}>{rank.name}</a> : rank.name}</dt>
            <dd>{rank.does}</dd>
          </div>
        ))}
      </dl>
      <p className="small">On the Discord, <code>/smp</code> has a few commands of its own:{" "}
        <a href="/guide/discord">Monkey SMP on Discord</a>.</p>
    </GuidePage>
  );
}
