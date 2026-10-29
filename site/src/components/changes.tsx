import { Children, isValidElement, type ReactNode } from "react";
import { dayLabel } from "@/lib/config";

/** One update in the player changelog (src/content/changes.mdx): its date on a stone tag, its title, and the
 * list under it. An update not released yet has no date and says so in its label ("Next update"). */
export function Entry({ date, label, title, children }:
  { date?: string; label?: string; title: string; children: ReactNode }) {
  return (
    <article>
      <h3>
        <time className="label" dateTime={date}>{label ?? (date ? dayLabel(date) : "Next update")}</time>
        {title}
      </h3>
      {children}
    </article>
  );
}

/** A line of a changelog entry. A line that is bold all through (`- **Update the modpack.**`) is the one to act
 * on: it gets the .todo style (bold, with a gold marker). */
export function ChangeLine({ children }: { children?: ReactNode }) {
  const parts = Children.toArray(children).filter((c) => !(typeof c === "string" && c.trim() === ""));
  const [only] = parts;
  if (parts.length === 1 && isValidElement<{ children?: ReactNode }>(only) && only.type === "strong") {
    return <li className="todo">{only.props.children}</li>;
  }
  return <li>{children}</li>;
}
