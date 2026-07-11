import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { DEFAULT_V3_THEME_ID, listV3Themes } from "@/modules/resume/themes";
import type { MujiThemeId } from "@/modules/resume/renderer/types";

export interface DeriveGuidanceContinueOpts {
  action: string;
  template_id?: string;
  target_page_count?: 1 | 2 | 3;
}

interface Props {
  open: boolean;
  runId?: string;
  onClose: () => void;
  onContinue: (opts: DeriveGuidanceContinueOpts) => void;
}

export function DeriveGuidance({ open, runId, onClose, onContinue }: Props) {
  const [templateId, setTemplateId] = useState<MujiThemeId>(DEFAULT_V3_THEME_ID);
  const [pages, setPages] = useState<1 | 2 | 3>(1);

  if (!open) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="页数校准引导"
      footer={<Button variant="secondary" onClick={onClose}>关闭</Button>}
    >
      <div className="space-y-4" data-testid="derive-guidance">
        <p className="text-sm text-muted-foreground">
          当前页数与目标不一致。可选择以下方式继续调整{runId ? "（将重新排队派生任务）" : ""}。
        </p>

        <div className="space-y-3">
          <div className="rounded border p-3 space-y-2">
            <p className="text-sm font-medium">切换简历主题</p>
            <select
              className="w-full rounded border px-2 py-1 text-sm"
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value as MujiThemeId)}
            >
              {listV3Themes().map((theme) => (
                <option key={theme.id} value={theme.id}>{theme.name}</option>
              ))}
            </select>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onContinue({ action: "switch_template", template_id: templateId })}
            >
              应用主题并继续
            </Button>
          </div>

          <div className="rounded border p-3 space-y-2">
            <p className="text-sm font-medium">调整目标页数</p>
            <div className="flex gap-2">
              {([1, 2, 3] as const).map((n) => (
                <Button
                  key={n}
                  size="sm"
                  variant={pages === n ? "primary" : "secondary"}
                  onClick={() => setPages(n)}
                >
                  {n} 页
                </Button>
              ))}
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                onContinue({ action: "change_target_pages", target_page_count: pages })
              }
            >
              应用页数并继续
            </Button>
          </div>

          <div className="rounded border p-3 space-y-2">
            <p className="text-sm font-medium">隐藏部分模块</p>
            <p className="text-xs text-muted-foreground">
              可在左侧模块面板关闭低优先级区块（如志愿者、兴趣等），再重新测量页数。
            </p>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onContinue({ action: "hide_modules" })}
            >
              我知道了，手动隐藏模块
            </Button>
          </div>

          <div className="rounded border p-3 space-y-2">
            <p className="text-sm font-medium">重试自动校准</p>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onContinue({ action: "retry" })}
            >
              重新排队派生
            </Button>
          </div>
        </div>

      </div>
    </Modal>
  );
}
