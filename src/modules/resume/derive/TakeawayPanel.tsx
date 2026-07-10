import { useEffect, useState } from "react";
import { getDeriveRationale } from "./api";

interface Props {
  resumeId: string;
}

export function TakeawayPanel({ resumeId }: Props) {
  const [notes, setNotes] = useState<string[]>([]);
  const [unused, setUnused] = useState<unknown[]>([]);

  useEffect(() => {
    getDeriveRationale(resumeId)
      .then((r) => {
        setNotes(r.takeaway_notes || []);
        setUnused(r.unused_materials || []);
      })
      .catch(() => {
        setNotes([]);
        setUnused([]);
      });
  }, [resumeId]);

  return (
    <div className="space-y-2 text-sm" data-testid="takeaway-panel">
      <h3 className="font-medium">为什么这么写</h3>
      {notes.length === 0 ? (
        <p className="text-muted-foreground">暂无取舍说明</p>
      ) : (
        <ul className="list-disc space-y-1 pl-4">
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {unused.length > 0 && (
        <p className="text-muted-foreground">未采用素材 {unused.length} 项（可回看，未静默丢弃）</p>
      )}
    </div>
  );
}
