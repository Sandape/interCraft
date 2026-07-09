import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { InterviewNewEntry } from '@/App'

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

describe('InterviewNewEntry', () => {
  it('redirects the legacy bare create route to mode selection and preserves query params', async () => {
    render(
      <MemoryRouter initialEntries={['/interview/new?job_id=job-1&branch_id=branch-1']}>
        <Routes>
          <Route path="/interview/new" element={<InterviewNewEntry />} />
          <Route path="/interview/mode" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent(
        '/interview/mode?job_id=job-1&branch_id=branch-1',
      )
    })
  })
})
