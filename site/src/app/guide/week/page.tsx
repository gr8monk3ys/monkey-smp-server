import { guideMetadata, GuidePage } from "@/components/guide-page";
import { ConfigLink } from "@/components/links";
import { Place } from "@/components/place";
import { week } from "@/content/guide/week";
import WeekNotes from "@/content/guide/week-notes.mdx";

export const metadata = guideMetadata("/guide/week");

export default function WeekPage() {
  return (
    <GuidePage href="/guide/week" lede="The same rhythm every week of the season. Times are Pacific.">
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
      <p className="small">The Town Crier at spawn has the next two Saturday events.</p>
      <p className="small">
        Want them on your phone? <ConfigLink to="CALENDAR_URL">Add Season I to your calendar</ConfigLink>: the
        launch, each Saturday&apos;s event and each Sunday&apos;s standings close, in your own time zone. It is a
        plain calendar file (.ics) that most calendar apps open.
      </p>
      <div className="prose"><WeekNotes /></div>
    </GuidePage>
  );
}
