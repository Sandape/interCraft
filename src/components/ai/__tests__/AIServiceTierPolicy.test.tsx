import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AIServiceTierSelector } from '../AIServiceTierSelector'

describe('AIServiceTierSelector', () => {
  it('renders standard/quality without provider names', () => {
    render(
      <AIServiceTierSelector
        value="standard"
        onChange={() => undefined}
        pointCapHint={{ standard: 10, quality: 25 }}
      />,
    )
    expect(screen.getByTestId('ai-service-tier-standard')).toBeInTheDocument()
    expect(screen.getByTestId('ai-service-tier-quality')).toBeInTheDocument()
    expect(screen.queryByText(/openai|anthropic|gpt|claude/i)).toBeNull()
  })

  it('notifies tier and degrade consent changes', () => {
    const onChange = vi.fn()
    const onAllowDegradeChange = vi.fn()
    render(
      <AIServiceTierSelector
        value="standard"
        onChange={onChange}
        allowDegrade={false}
        onAllowDegradeChange={onAllowDegradeChange}
      />,
    )
    fireEvent.click(screen.getByTestId('ai-service-tier-quality'))
    expect(onChange).toHaveBeenCalledWith('quality')
    fireEvent.click(screen.getByTestId('ai-service-tier-degrade-input'))
    expect(onAllowDegradeChange).toHaveBeenCalledWith(true)
  })
})
