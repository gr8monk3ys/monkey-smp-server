// The Reports tab (tools/staff_report.py answers it): each week's rule check as a grid of players and rules, the rows
// behind a cell, the checks that came back clean, and the week as text to paste into Discord. It only shows:
// nothing here punishes, messages or rolls anything back.
import { useEffect, useRef, useState, type ButtonHTMLAttributes } from "react";
import { Copy, RefreshCw } from "lucide-react";
import { get, query } from "../../lib/api";
import { useMessages, useOnShow } from "../../lib/hooks";
import type { TabProps } from "../../shell/tabs";
import { Actions, Button, Empty, Fine, Fold, Message, Messages, PageHead, Panel, Panels, Row, Rows, Select, TableScroll, cx } from "../../ui/kit";
import { LEVELS, also, day, discord, span } from "./discord";

const CELL = "min-h-9 min-w-10 px-2 font-bold border-2 aria-pressed:outline-2 aria-pressed:outline-offset-2 aria-pressed:outline-bone";
const CELL_LOOK: Record<string, string> = {
  clear: "bg-gold border-gold text-ink",
  likely: "bg-line-1 border-line-1 text-ink",
  unclear: "border-dashed border-bone-2 text-bone",
};

/** A number in a box whose look says how sure the finding is: solid gold clear, amber likely, dashed unclear. */
function Cell({ level, children, ...rest }: { level: string; children: string } & ButtonHTMLAttributes<HTMLButtonElement>) {
  if (!rest.onClick) {
    return <span className={cx(CELL, "inline-flex items-center justify-center", CELL_LOOK[level])}>{children}</span>;
  }
  return (
    <button type="button" className={cx(CELL, "cursor-pointer hover:border-bone", CELL_LOOK[level])} {...rest}>
      {children}
    </button>
  );
}

export default function ReportsTab({ active }: TabProps) {
  const m = useMessages();
  const [weeks, setWeeks] = useState<any[] | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [report, setReport] = useState<any | null>(null);
  const [cell, setCell] = useState<{ player: any; check: any; cell: any } | null>(null);
  const [messages, setMessages] = useState<string[] | null>(null);
  const [copied, setCopied] = useState<Record<number, string>>({});
  const loaded = useRef(false);
  const current = useRef<string | null>(null);
  const evidence = useRef<HTMLDivElement>(null);

  const open = async (week: string) => {
    current.current = week;
    setPicked(week);
    m.clear();
    setMessages(null);
    setCell(null);
    try {
      const data = await get(`/api/report?${query({ week })}`);
      if (current.current !== week) return;    // another week was picked while this one loaded
      setReport(data.report);
    } catch (e) {
      if (current.current === week) m.fail(e);
    }
  };

  const load = async () => {
    loaded.current = true;
    m.clear();
    let list: any[];
    try {
      list = (await get("/api/reports")).weeks || [];
    } catch (e) {
      loaded.current = false;
      m.fail(e);
      return;
    }
    setWeeks(list);
    if (!list.length) {
      setReport(null);
      return;
    }
    await open(list.some((w) => w.week === current.current) ? (current.current as string) : list[0].week);
  };

  useOnShow(() => {
    if (!loaded.current) void load();
  }, active);

  useEffect(() => {
    if (cell) evidence.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [cell]);

  const copy = async (text: string, i: number) => {
    let note: string;
    try {
      await navigator.clipboard.writeText(text);
      note = "Copied. Paste it into Discord.";
    } catch {
      note = "The browser didn't allow copying: select the text and copy it.";
    }
    setCopied((c) => ({ ...c, [i]: note }));
  };

  const showDiscord = () => {
    if (!report) return;
    const list = discord(report);
    setMessages(list);
    setCopied({});
    void copy(list[0], 0);
  };

  const none = weeks !== null && weeks.length === 0;
  const made = report?.made ? new Date(report.made) : null;

  return (
    <>
      <PageHead title="Reports">
        <p>
          Each Monday the server's own logs are checked against the rules for the week before: Ledger, the players'
          stats, the parties and the game log. It only reports. Nothing here punishes, messages or rolls back anyone:
          read the rows behind a number before you act on it.
        </p>
      </PageHead>
      <div className="mb-4 flex flex-col gap-3">
        <Messages of={m} />
        <Actions>
          <Select
            aria-label="Week"
            className="min-w-0 flex-1 basis-72"
            disabled={!weeks?.length}
            value={picked ?? ""}
            onChange={(e) => void open(e.target.value)}
            options={(weeks || []).map((w) => ({
              value: w.week,
              label: `${w.week}: ${day(w.from)}, ${w.players} players, ${w.clear + w.likely} clear or likely`,
            }))}
          />
          <Button kind="primary" icon={<Copy />} disabled={!weeks?.length || !report} onClick={showDiscord}>Copy for Discord</Button>
          <Button
            icon={<RefreshCw />}
            onClick={() => {
              loaded.current = false;
              void load();
            }}
          >
            Reload
          </Button>
        </Actions>
        {none && (
          <Message kind="note">
            No week written yet. The weekly job writes one each Monday for the week before (sudo sh
            /srv/monkey/repo/deploy/monkey-report.sh --install).
          </Message>
        )}
      </div>

      {report && (
        <div className="flex flex-col gap-4">
          <Panel title={report.week} meta={span(report)}>
            <Fine>
              {`Written ${made && !Number.isNaN(made.getTime()) ? made.toLocaleString() : "at a time that can't be read"}.`}
              {report.partial ? ` Not a whole week: ${report.partial}.` : ""}
            </Fine>
            <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sage" aria-label="How sure each number is">
              <li className="inline-flex items-center gap-2"><Cell level="clear">3</Cell> clear in the logs</li>
              <li className="inline-flex items-center gap-2"><Cell level="likely">3</Cell> likely: something the logs can't see could explain it</li>
              <li className="inline-flex items-center gap-2"><Cell level="unclear">3</Cell> unclear: worth a look, no more</li>
            </ul>
            {report.players.length === 0 ? (
              <Message kind="note">Nobody: every check came back clean.</Message>
            ) : (
              <TableScroll label="Players and rules">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Player</th>
                      {report.checks.map((c: any) => (
                        <th key={c.id} scope="col" className="align-bottom">
                          <span className="block text-bone">{c.title}</span>
                          <span className="block text-[0.8125rem] font-normal text-sage">{c.rule}</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.players.map((p: any) => (
                      <tr key={p.name}>
                        <th scope="row" className="font-bold">{p.name}</th>
                        {report.checks.map((c: any) => {
                          const cl = p.cells[c.id];
                          return (
                            <td key={c.id}>
                              {cl && (
                                <Cell
                                  level={cl.level}
                                  aria-pressed={cell?.cell === cl ? true : undefined}
                                  aria-label={`${p.name}, ${c.title} (${c.rule}): ${cl.what} ${cl.count}, ${LEVELS[cl.level]}${also(cl)}`}
                                  title={`${cl.what}: ${cl.count}, ${LEVELS[cl.level]}${also(cl)}`}
                                  onClick={() => setCell({ player: p, check: c, cell: cl })}
                                >
                                  {String(cl.count)}
                                </Cell>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableScroll>
            )}
          </Panel>

          {cell && (
            <div ref={evidence}>
              <Panel
                title={`${cell.player.name}: ${cell.check.title}`}
                meta={`(${cell.check.rule})`}
                aside={<Button small onClick={() => setCell(null)}>Close</Button>}
              >
                <Fine>
                  {`${cell.cell.what}: ${cell.cell.count}, ${LEVELS[cell.cell.level]}${also(cell.cell)}.`}
                  {cell.cell.more ? ` The first ${cell.cell.evidence.length} rows; ${cell.cell.more} more are in the file.` : ""}
                </Fine>
                <TableScroll label="The rows behind it">
                  <table className="data">
                    <thead>
                      <tr><th>When (Pacific)</th><th>World</th><th>Where</th><th>What happened</th><th>How sure</th></tr>
                    </thead>
                    <tbody>
                      {cell.cell.evidence.map((e: any, i: number) => (
                        <tr key={i}>
                          <td className="whitespace-nowrap">{e.time || ""}</td>
                          <td>{e.world || ""}</td>
                          <td className="mono whitespace-nowrap">{e.pos ? e.pos.join(" ") : ""}</td>
                          <td className="min-w-72 whitespace-normal wrap-anywhere">{e.what}</td>
                          <td>{e.level}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableScroll>
              </Panel>
            </div>
          )}

          {messages && (
            <Panel title="For Discord">
              <Fine>The first message is copied already. Paste each one in order.</Fine>
              {messages.map((text, i) => (
                <div key={i} className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h4>{`Message ${i + 1} of ${messages.length}, ${text.length} characters`}</h4>
                    <Button small icon={<Copy />} onClick={() => void copy(text, i)}>Copy</Button>
                  </div>
                  <pre className="log h-auto! max-h-80">{text}</pre>
                  {copied[i] && <Message kind="note">{copied[i]}</Message>}
                </div>
              ))}
            </Panel>
          )}

          <Panels>
            <Panel title="Read this first">
              <Rows>
                {(report.notes || []).map((n: string, i: number) => (
                  <Row key={i}><span className="whitespace-pre-wrap wrap-anywhere">{n}</span></Row>
                ))}
                {!(report.notes || []).length && <Empty>Nothing to note.</Empty>}
              </Rows>
            </Panel>
            <Panel title="Checked and clean">
              <Rows>
                {(report.clean || []).map((c: any, i: number) => <Row key={i} title={c.title} about={`${c.rule}: ${c.result}`} />)}
                {!(report.clean || []).length && <Empty>Nothing came back clean this week.</Empty>}
              </Rows>
            </Panel>
            {(report.skipped || []).length > 0 && (
              <Panel title="Not checked" wide>
                <Rows>
                  {report.skipped.map((s: any, i: number) => <Row key={i}>{`${s.title}: ${s.why}`}</Row>)}
                </Rows>
              </Panel>
            )}
          </Panels>

          {(report.mining || []).length > 0 && (
            <Panel>
              <Fold title="Mining: diamond ore and ancient debris per 1,000 stone">
                <TableScroll label="Mining">
                  <table className="data">
                    <thead>
                      <tr><th>Player</th><th>Stone</th><th>Diamond ore</th><th>Ancient debris</th><th>Per 1,000</th></tr>
                    </thead>
                    <tbody>
                      {report.mining.map((r: any) => (
                        <tr key={r.name}>
                          <td>{r.name}</td><td>{String(r.stone)}</td><td>{String(r.diamond)}</td><td>{String(r.debris)}</td>
                          <td>{r.per_k === null ? "" : String(r.per_k)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableScroll>
              </Fold>
            </Panel>
          )}
        </div>
      )}
    </>
  );
}
