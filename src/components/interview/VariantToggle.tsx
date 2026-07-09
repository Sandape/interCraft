/**
 * [REQ-048 US5 T102] VariantToggle component — UI toggle for 变体 toggle.
 *
 * Renders a switch + hover description. When enabled, the upcoming
 * 「快速补漏」session uses LLM-generated question variants instead of
 * the original question_text from the error_questions table.
 *
 * zh-CN copy:
 * - enabled state: 「变体重考已开启：每道错题将由 AI 生成新的问法，考察点保持不变」
 * - disabled state: 「原题重考：直接使用错题原题（默认 — 节省 token）」
 * - hover description: 「变体重考会消耗额外的 LLM 配额（约 5 次调用/5 道题），请仅在需要时启用」
 *
 * The component is purely presentational; the parent (DrillCandidatesPreview)
 * handles the onChange callback to write the boolean into the
 * ``use_variants`` field of the start-interview API request body.
 *
 * Test ID surface (used by tests/e2e/variant-toggle.spec.ts):
 * - data-testid="variant-toggle"
 * - data-testid="variant-toggle-switch"
 * - data-testid="variant-toggle-description"
 * - role="switch"
 * - aria-checked={enabled}
 */
import React from 'react';

export interface VariantToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  /** Optional disabled flag (e.g., user has 0 errors). */
  disabled?: boolean;
}

const ENABLED_COPY = '变体重考已开启：每道错题将由 AI 生成新的问法，考察点保持不变';
const DISABLED_COPY = '原题重考：直接使用错题原题（默认 — 节省 token）';
const HOVER_DESCRIPTION =
  '变体重考会消耗额外的 LLM 配额（约 5 次调用/5 道题），请仅在需要时启用';

export const VariantToggle: React.FC<VariantToggleProps> = ({
  enabled,
  onChange,
  disabled = false,
}) => {
  const copy = enabled ? ENABLED_COPY : DISABLED_COPY;

  const handleClick = () => {
    if (!disabled) {
      onChange(!enabled);
    }
  };

  return (
    <div
      className="variant-toggle"
      data-testid="variant-toggle"
      data-enabled={enabled}
      onMouseDown={(e) => e.preventDefault()}
      onClick={handleClick}
      title={HOVER_DESCRIPTION}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '12px 16px',
        border: '1px solid #d9d9d9',
        borderRadius: 8,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        backgroundColor: enabled ? '#f0f5ff' : '#fafafa',
      }}
    >
      <span
        data-testid="variant-toggle-switch"
        role="switch"
        aria-checked={enabled}
        aria-label="换种问法"
        style={{
          width: 36,
          height: 20,
          borderRadius: 10,
          backgroundColor: enabled ? '#1677ff' : '#bfbfbf',
          position: 'relative',
          transition: 'background-color 0.2s',
          flexShrink: 0,
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: 2,
            left: enabled ? 18 : 2,
            width: 16,
            height: 16,
            borderRadius: '50%',
            backgroundColor: '#fff',
            transition: 'left 0.2s',
          }}
        />
      </span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 500, fontSize: 14 }}>换种问法</div>
        <div
          data-testid="variant-toggle-description"
          style={{ fontSize: 12, color: '#666', marginTop: 2 }}
        >
          {copy}
        </div>
      </div>
    </div>
  );
};

export default VariantToggle;