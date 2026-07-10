import { useEffect, useState } from "react";
import { getDeriveRationale } from "./api";

interface UnusedItem {
  ref?: string;
  reason?: string;
  section?: string;
}

interface Props {
  resumeId: string;
}

export function UnusedMaterialsPanel({ resumeId }: Props) {
  const [items, setItems] = useState<UnusedItem[]>([]);

  useEffect(() => {
    getDeriveRationale(resumeId)
      .then((r) => setItems((r.unused_materials as UnusedItem[]) || []))
      .catch(() => setItems([]));
  }, [resumeId]);

  return (
    <div className="space-y-2 text-sm" data-testid="unused-materials-panel">
      <h3 className="font-medium">未采用素材</h3>
      <p className="text-muted-foreground text-xs">
        派生时因篇幅或相关度未写入正文，仍可回看，未静默丢弃。
      </p>
      {items.length === 0 ? (
        <p className="text-muted-foreground">暂无未采用素材</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, idx) => (
            <li key={item.ref || idx} className="rounded border px-2 py-1.5">
              <div className="font-medium">{item.section || "素材"}</div>
              {item.ref && (
                <div className="text-xs text-muted-foreground truncate">{item.ref}</div>
              )}
              {item.reason && (
                <div className="text-xs text-muted-foreground">原因：{item.reason}</div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
