import { Fragment } from "react";
import { guideMetadata, GuidePage } from "@/components/guide-page";
import { type Command, roles } from "@/content/guide/commands";

export const dynamicParams = false;

export function generateStaticParams() {
  return roles.map((role) => ({ rank: role.id }));
}

export async function generateMetadata({ params }: PageProps<"/guide/commands/[rank]">) {
  return guideMetadata(`/guide/commands/${(await params).rank}`);
}

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

export default async function Rank({ params }: PageProps<"/guide/commands/[rank]">) {
  const { rank } = await params;
  const role = roles.find((r) => r.id === rank)!;
  return (
    <GuidePage href={`/guide/commands/${role.id}`} lede={role.intro}>
      {role.groups.map((group, i) => (
        <Fragment key={i}>
          {group.heading && <h2>{group.heading}</h2>}
          {group.note && <p className="small">{group.note}</p>}
          {group.text && <p>{group.text}</p>}
          {group.cmds && <Commands cmds={group.cmds} />}
        </Fragment>
      ))}
      {role.after && <p className="small after">{role.after}</p>}
    </GuidePage>
  );
}
