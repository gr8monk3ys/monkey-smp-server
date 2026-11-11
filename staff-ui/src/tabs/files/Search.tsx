// The search of all files (tools/staff_desk.py): by name, or by what is written in the settings files. A result
// opens in the editor (the Files tab hears it on the bus).
import { useState } from "react";
import { get, query } from "../../lib/api";
import { emit } from "../../lib/bus";
import { useMessages } from "../../lib/hooks";
import { Button, Check, Empty, Fine, FormRow, Input, Messages, Panel, Row, Rows } from "../../ui/kit";

interface Result {
  path: string;
  line?: number;
  text?: string;
}

export default function Search() {
  const m = useMessages();
  const [q, setQ] = useState("");
  const [inText, setInText] = useState(false);
  const [results, setResults] = useState<Result[] | null>(null);
  const [cut, setCut] = useState(false);

  const go = async () => {
    const wanted = q.trim();
    if (wanted.length < 2) {
      m.clear();
      m.fail("Search for at least 2 characters.");
      return;
    }
    await m.run(async () => {
      const data = await get(`/api/file-search?${query({ q: wanted, text: inText ? "1" : "0" })}`);
      setResults(data.results || []);
      setCut(Boolean(data.cut));
    });
  };

  return (
    <Panel title="Search all files" wide>
      <Fine>
        Every file in the server's folder that the page can open, by name, or with "In the text" by what is written in its
        settings files. Secrets in a line found stay hidden.
      </Fine>
      <Messages of={m} />
      <FormRow>
        <Input
          type="search"
          maxLength={100}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go()}
          placeholder="e.g. view-distance or claims"
          aria-label="What to search for"
        />
        <Check label="In the text" checked={inText} onChange={(e) => setInText(e.target.checked)} />
        <Button kind="primary" onClick={go} disabled={m.busy}>
          Search
        </Button>
      </FormRow>
      {results && results.length > 0 && (
        <Fine role="status">
          {results.length} found
          {cut ? ": the search stopped early, so there may be more. Search for something longer." : "."}
        </Fine>
      )}
      {results && (
        <Rows label="Search results">
          {results.length === 0 && <Empty>Nothing found.</Empty>}
          {results.map((r, i) => (
            <Row
              key={`${r.path}:${r.line ?? ""}:${i}`}
              title={
                <Button kind="link" className="font-mono wrap-anywhere text-left" onClick={() => emit("open-file", { path: r.path, writable: true })}>
                  {r.line ? `${r.path}, line ${r.line}` : r.path}
                </Button>
              }
              about={r.text ? <span className="font-mono wrap-anywhere">{r.text}</span> : undefined}
            />
          ))}
        </Rows>
      )}
    </Panel>
  );
}
