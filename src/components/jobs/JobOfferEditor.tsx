/** 024 US1 — Offer section editor with 4 fields + deadline validation. */
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

interface OfferData {
  offer_salary_text: string | null
  offer_contact_name: string | null
  offer_contact_info: string | null
  offer_deadline_at: string | null
}

interface Props {
  initial: OfferData
  onSave: (data: OfferData) => Promise<void>
  onCancel: () => void
}

export function JobOfferEditor({ initial, onSave, onCancel }: Props) {
  const [salaryText, setSalaryText] = useState(initial.offer_salary_text ?? '')
  const [contactName, setContactName] = useState(initial.offer_contact_name ?? '')
  const [contactInfo, setContactInfo] = useState(initial.offer_contact_info ?? '')
  const [deadlineAt, setDeadlineAt] = useState(initial.offer_deadline_at ? initial.offer_deadline_at.slice(0, 10) : '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave() {
    setError(null)
    if (deadlineAt) {
      const d = new Date(deadlineAt)
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      if (d < today) {
        setError('截止日期不能早于今天')
        return
      }
    }
    setSaving(true)
    try {
      await onSave({
        offer_salary_text: salaryText.trim() || null,
        offer_contact_name: contactName.trim() || null,
        offer_contact_info: contactInfo.trim() || null,
        offer_deadline_at: deadlineAt ? new Date(deadlineAt + 'T23:59:59Z').toISOString() : null,
      })
    } catch (e: unknown) {
      setError((e as Error)?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-3" data-testid="job-offer-editor">
      <h3 className="text-sm font-medium text-ink-1">Offer 信息</h3>
      <div>
        <label className="block text-xs font-medium text-ink-2 mb-1">薪资</label>
        <Input
          value={salaryText}
          onChange={(e) => setSalaryText(e.target.value)}
          placeholder="如：30-50K · 16薪"
          maxLength={200}
          data-testid="offer-salary-text"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1">联系人</label>
          <Input
            value={contactName}
            onChange={(e) => setContactName(e.target.value)}
            placeholder="如：张经理"
            maxLength={100}
            data-testid="offer-contact-name"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1">联系方式</label>
          <Input
            value={contactInfo}
            onChange={(e) => setContactInfo(e.target.value)}
            placeholder="如：zhang@example.com"
            maxLength={200}
            data-testid="offer-contact-info"
          />
        </div>
      </div>
      <div>
        <label className="block text-xs font-medium text-ink-2 mb-1">截止日期</label>
        <Input
          type="date"
          value={deadlineAt}
          onChange={(e) => setDeadlineAt(e.target.value)}
          data-testid="offer-deadline-at"
        />
      </div>
      {error && (
        <p className="text-xs text-red-500" data-testid="offer-editor-error">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="ghost" onClick={onCancel} disabled={saving}>
          取消
        </Button>
        <Button variant="primary" onClick={handleSave} loading={saving} data-testid="offer-save-btn">
          保存
        </Button>
      </div>
    </div>
  )
}
