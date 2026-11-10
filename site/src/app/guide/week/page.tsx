import { guideMetadata, GuidePage } from "@/components/guide-page";
import { ConfigLink } from "@/components/links";
import { Live, OffNote } from "@/components/live";
import { Place } from "@/components/place";
import { week } from "@/content/guide/week";
import WeekNotes from "@/content/guide/week-notes.mdx";
import { running } from "@/lib/live";

export const metadata = guideMetadata("/guide/week");

export default function WeekPage() {
  return (
    <GuidePage href="/guide/week" lede="The same rhythm every week of the season. Times are Pacific.">
      {/* In a div of its own, so the note lets only itself name what isn't running (tools/live_packs.py). */}
      <div>
        <OffNote packs={["monkey-wardrobe", "monkey-drops", "monkey-omens", "monkey-events", "monkey-outposts",
          "monkey-standings", "monkey-firsts", "monkey-finale", "monkey-npcs"]} />
      </div>
      <Place as="ol" className="week">
        {week.map((day) => (
          <li key={day.name} className={day.place}>
            <h2>{day.name}</h2>
            {day.lines.map((line, i) => (
              <p key={i} className={line.quiet ? "quiet" : undefined}>
                {line.at && <span className="at">{line.at}</span>}{line.text}
              </p>
            ))}
          </li>
        ))}
      </Place>
      <Live pack="monkey-npcs"><p className="small">The Town Crier at spawn has the next two Saturday events.</p></Live>
      <p className="small">
        Want them on your phone? <ConfigLink to="CALENDAR_URL">Add Season I to your calendar</ConfigLink>: the
        launch{running("monkey-standings")
          ? <>, each Saturday&apos;s event and each Sunday&apos;s standings close,</>
          : <> and each Saturday&apos;s event,</>} in your own time zone. It is a plain calendar file (.ics) that most
        calendar apps open.
      </p>
      <div className="prose"><WeekNotes /></div>
    </GuidePage>
  );
}
