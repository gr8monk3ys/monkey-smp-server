// Game rules, read from the running server; a change takes effect at once.
import { useState } from "react";
import { Button, Check, Field, Input, Message, Panel, cx } from "../../ui/kit";

function Rule({ rule, onSet }: { rule: any; onSet: (rule: any, value: boolean | number) => void }) {
  const [text, setText] = useState(String(rule.value ?? ""));
  const [on, setOn] = useState(rule.value === true);
  const about = rule.missing ? `${rule.about} Not on this server.` : rule.about;
  const set = () => {
    const t = text.trim();
    const n = Number(t);
    onSet(rule, t === "" || Number.isNaN(n) ? NaN : n);
  };
  return (
    <Field label={<span className="font-mono">{rule.name}</span>} help={about} className={cx("py-1", rule.missing && "opacity-60")}>
      {(id) =>
        rule.type === "bool" ? (
          <Check
            id={id}
            checked={on}
            disabled={rule.missing}
            label={on ? "on" : "off"}
            onChange={(e) => {
              setOn(e.target.checked);
              onSet(rule, e.target.checked);
            }}
          />
        ) : (
          <div className="flex flex-wrap gap-2">
            <Input
              id={id}
              type="number"
              className="w-40"
              min={rule.min}
              max={rule.max}
              step={1}
              value={text}
              disabled={rule.missing}
              need="admin"
              onChange={(e) => setText(e.target.value)}
            />
            <Button need="admin" disabled={rule.missing} onClick={set}>
              Set
            </Button>
          </div>
        )
      }
    </Field>
  );
}

export default function GameRules({ rules, error, onSet }: { rules: any[] | null; error: string; onSet: (rule: any, value: boolean | number) => void }) {
  return (
    <Panel wide title="Game rules">
      <p className="fine">
        Read from the running server. A change takes effect at once, no restart. The launch, Truce Hour and season events switch some rules themselves (pvp,
        portals) and may switch them back.
      </p>
      <Message kind="error">{error}</Message>
      <div className="grid grid-cols-1 gap-x-6 gap-y-3 md:grid-cols-2 xl:grid-cols-3">
        {rules?.map((rule) => <Rule key={rule.name} rule={rule} onSet={onSet} />)}
      </div>
    </Panel>
  );
}
