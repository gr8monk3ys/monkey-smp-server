// What went wrong: the likely causes (tools/staff_watch.py's advice) and the recent problems from the log.
import type { ReactNode } from "react";
import { plural } from "../../lib/format";
import { agoMs } from "../../lib/status";
import { Fine, Mark, Panel, type MarkKind } from "../../ui/kit";
import { DAY_CLOCK } from "./charts";

const ERRORS_SHOWN = 8;          // the file keeps up to 30, newest first
const one = (n: number) => n.toFixed(1);

function Problem({ kind, label, when, text, bold, children }: { kind: MarkKind; label: string; when?: string; text?: string; bold?: boolean; children?: ReactNode }) {
  return (
    <li className="flex flex-col gap-0.5 py-2.5 first:pt-0 not-first:border-t-2 not-first:border-leaf-2">
      <p className="flex flex-wrap items-baseline gap-x-2">
        <Mark kind={kind} className="self-center" />
        <span className="font-bold text-bone">{label}</span>
        {when && <span className="text-[0.9375rem] text-sage">{when}</span>}
      </p>
      {text && <p className={bold ? "font-bold text-bone wrap-anywhere" : "text-bone-2 wrap-anywhere"}>{text}</p>}
      {children}
    </li>
  );
}

function howOften(group: any, now: number): string {
  if (group.older) {
    const before = "before this page started watching";
    return group.count === 1 ? `Sometime ${before}` : `${plural(group.count, "time")} ${before}`;
  }
  const last = agoMs(now - Date.parse(group.last));
  if (group.count === 1) return last;
  return `${plural(group.count, "time")} since ${DAY_CLOCK.format(new Date(group.first))}, last ${last}`;
}

const ADVICE_MARKS: Record<string, [MarkKind, string]> = { alert: ["slow", "Needs a look"], warn: ["busy", "Worth a look"], info: ["good", "Usually harmless"] };

export function Advice({ data }: { data: any }) {
  const rows = (Array.isArray(data.advice) ? data.advice : []).filter((a: any) => a && a.title);
  if (!rows.length) return null;
  return (
    <Panel title="What it probably is">
      <ul className="m-0 list-none p-0">
        {rows.map((a: any, i: number) => {
          const [kind, word] = ADVICE_MARKS[a.level] || ADVICE_MARKS.warn;
          return (
            <Problem key={i} kind={kind} label={word} text={a.title} bold>
              {a.from && <p className="text-[0.9375rem] text-sage wrap-anywhere">{`From: ${a.from}`}</p>}
              {a.fix && <p className="text-bone-2 wrap-anywhere">{a.fix}</p>}
            </Problem>
          );
        })}
      </ul>
      <Fine>
        Read from the problems below and the machine's numbers. A guess from the words in the log, so check before acting
        on it. The staff channel hears of the serious ones.
      </Fine>
    </Panel>
  );
}

export function Problems({ data, now }: { data: any; now: number }) {
  const p = data.problems;
  const items: ReactNode[] = [];
  let fine = "";
  if (!p) {
    items.push(<Problem key="none" kind="unknown" label="No reading yet" text="The log hasn't been read yet." />);
  } else {
    if (!p.read || p.crashes === null) {
      items.push(
        <Problem key="partial" kind="unknown" label="Can't read everything"
          text={`The ${p.read ? "crash reports" : "server's log"} couldn't be read just now, so this list may be missing something.`} />,
      );
    }
    (p.crashes || []).forEach((crash: any, i: number) => {
      items.push(<Problem key={`c${i}`} kind="slow" label="Crashed" when={agoMs(now - Date.parse(crash.when))} text={crash.text} />);
    });
    if (p.lag) {
      items.push(
        <Problem key="lag" kind="busy" label="Fell behind" when={howOften(p.lag, now)}
          text={`The worst was ${one(p.lag.worst / 1000)} seconds behind. Players feel this as a freeze.`} />,
      );
    }
    const errors: any[] = p.errors || [];
    errors.slice(0, ERRORS_SHOWN).forEach((group, i) => {
      items.push(<Problem key={`e${i}`} kind="busy" label="Error" when={howOften(group, now)} text={group.text} />);
    });
    if (errors.length > ERRORS_SHOWN) {
      items.push(<li key="more" className="py-2.5 text-sage">{`and ${errors.length - ERRORS_SHOWN} more`}</li>);
    }
    if (!items.length) items.push(<Problem key="fine" kind="good" label="Nothing in the last 24 hours" />);
    const startup = p.log && p.log.startup;
    fine = "Errors since the server finished starting, stalls of 2 seconds or more, and crashes. "
      + `Warnings aren't listed${startup ? `, nor the ${plural(startup, "error")} from its last start: this pack logs about that many each time` : ""}. `
      + "The full story is in the server's log.";
  }
  return (
    <Panel title="Recent problems">
      <ul className="m-0 list-none p-0">{items}</ul>
      {fine && <Fine>{fine}</Fine>}
    </Panel>
  );
}
