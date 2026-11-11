// The history of changes to files: every save, delete and rename is kept, and an entry can be put back.
import { useCallback, useEffect, useState } from "react";
import { get, listOf, post } from "../../lib/api";
import { when } from "../../lib/format";
import type { Ask } from "../../ui/kit";
import { Button, Empty, Fold, Row, Rows } from "../../ui/kit";

interface Entry {
  entry: string;
  path: string;
  user?: string;
  time?: unknown;
}

export default function History({ active, refresh, ask, onError, onNote }: {
  active: boolean;
  /** Changes when a file was changed here, so an open history reads itself again. */
  refresh: number;
  ask: (ask: Ask) => void;
  onError: (e: unknown) => void;
  onNote: (text: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Entry[] | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await get("/api/history");
      setRows(
        listOf<any>(data, "entries").map((raw) => {
          const h = typeof raw === "string" ? { entry: raw } : raw;
          return { entry: h.entry || h.id || h.name || "", path: h.path || "", user: h.user, time: h.time };
        }),
      );
    } catch (e) {
      onError(e);
    }
  }, [onError]);

  useEffect(() => {
    if (open && active) void load();
  }, [open, active, refresh, load]);

  return (
    <Fold title="History of changes to files" open={open} onToggle={setOpen}>
      <Rows label="History of changes to files">
        {rows && rows.length === 0 && <Empty>No changes yet.</Empty>}
        {rows?.map((h, i) => {
          const meta = [h.user, h.time ? when(h.time) : "", h.path ? h.entry : ""].filter(Boolean).join(", ");
          return (
            <Row
              key={`${h.entry}:${i}`}
              title={<span className="font-mono wrap-anywhere">{h.path || h.entry}</span>}
              about={meta}
              actions={
                h.entry && h.path ? (
                  <Button
                    small
                    onClick={() =>
                      ask({
                        message: `Put back ${h.path} from this entry? The file as it is now goes to history first.`,
                        yes: "Yes, restore",
                        onYes: async () => {
                          try {
                            await post("/api/restore", { entry: h.entry, path: h.path });
                            onNote(`Restored ${h.path}. Most changes take effect after a restart.`);
                            void load();
                          } catch (e) {
                            onError(e);
                          }
                        },
                      })
                    }
                  >
                    Restore
                  </Button>
                ) : undefined
              }
            />
          );
        })}
      </Rows>
    </Fold>
  );
}
