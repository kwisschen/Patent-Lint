// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Two result cards used to return early BEFORE their hooks. A card that
// mounted with nothing to show and then received findings called more hooks
// on the second render than on the first, and React threw "Rendered more
// hooks than during the previous render". ESLint's rules-of-hooks found both
// once lint actually ran (it never had: eslint was not in package.json).
//
// These render each card empty, then populated, in the same root.
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AntecedentBasisCard from '../components/AntecedentBasisCard'
import RubricHero from '../components/RubricHero'
import { FeedbackProvider } from '../components/FeedbackPicker'

describe('cards keep the same hook order from empty to populated', () => {
  it('AntecedentBasisCard', () => {
    const issue = { claim_id: 1, term: 'widget', reference_form: 'the widget' }
    const wrap = (issues) => (
      <FeedbackProvider>
        <AntecedentBasisCard issues={issues} claimTrees={[]} jurisdiction="US" />
      </FeedbackProvider>
    )
    const { rerender, container } = render(wrap([]))
    expect(container.textContent).toBe('')
    expect(() => rerender(wrap([issue]))).not.toThrow()
    expect(container.textContent).not.toBe('')
  })

  it('RubricHero', () => {
    const empty = { specification_checks: [] }
    const populated = {
      rubric_grade: { letter: 'B', score: 85 },
      specification_checks: [{ status: 'pass' }, { status: 'amend' }],
    }
    const wrap = (data) => (
      <MemoryRouter>
        <RubricHero data={data} />
      </MemoryRouter>
    )
    const { rerender, container } = render(wrap(empty))
    expect(container.textContent).toBe('')
    expect(() => rerender(wrap(populated))).not.toThrow()
    expect(container.textContent).not.toBe('')
  })
})
