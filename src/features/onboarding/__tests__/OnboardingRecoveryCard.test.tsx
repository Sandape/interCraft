import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { OnboardingRecoveryCard } from '../OnboardingRecoveryCard'
import {
  createOnboardingState,
  markOnboardingActivated,
  markOnboardingSkipped,
  saveOnboardingState,
} from '../onboarding-state'

describe('OnboardingRecoveryCard', () => {
  beforeEach(() => window.localStorage.clear())

  it('offers a resume path for skipped onboarding', () => {
    saveOnboardingState(markOnboardingSkipped({ ...createOnboardingState(), currentStep: 3 }))

    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <OnboardingRecoveryCard />
      </MemoryRouter>,
    )

    expect(screen.getByText(/继续创建第一份岗位定制简历/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /继续引导/i })).toHaveAttribute(
      'href',
      '/onboarding?resume=1',
    )
  })

  it('stays out of the way after activation', () => {
    saveOnboardingState(markOnboardingActivated(createOnboardingState()))

    const { container } = render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <OnboardingRecoveryCard />
      </MemoryRouter>,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
